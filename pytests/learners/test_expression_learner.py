from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import asyncio
import threading

from sqlmodel import Session, SQLModel, create_engine, select
import pytest


@pytest.fixture(scope="module")
def learner_module(tmp_path_factory):
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("MAIBOT_INSTANCE_DIR", str(tmp_path_factory.mktemp("expression-instance")))
        from src.learners import expression_learner

        yield expression_learner


@pytest.fixture
def storage(learner_module, tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'expressions.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine, tables=[learner_module.Expression.__table__])
    state = SimpleNamespace(failure=None, threads=[])

    @contextmanager
    def db_session():
        state.threads.append(threading.get_ident())
        with Session(engine) as session:
            original_add = session.add
            additions = 0

            def add(record):
                nonlocal additions
                additions += 1
                if state.failure == "second_write" and additions == 2:
                    session.flush()
                    raise RuntimeError("second write failed")
                original_add(record)

            monkeypatch.setattr(session, "add", add)
            try:
                yield session
                if state.failure == "commit":
                    session.flush()
                    raise RuntimeError("commit failed")
                session.commit()
            except Exception:
                session.rollback()
                raise

    monkeypatch.setattr(learner_module, "get_db_session", db_session)
    yield engine, state
    engine.dispose()


@pytest.fixture
def learner(learner_module, monkeypatch):
    learner = learner_module.ExpressionLearner("test-session")
    sources = [SimpleNamespace(message_id=f"message-{index}", session_id="test-session") for index in range(10)]
    learner.pending_messages.extend(sources)
    monkeypatch.setattr(learner, "_resolve_learning_session_id", lambda _messages: "test-session")
    monkeypatch.setattr(learner, "_get_session_display_name", lambda _session_id: "测试群")
    monkeypatch.setattr(learner, "_prepare_learning_messages", lambda messages: messages)
    monkeypatch.setattr(learner, "_build_multi_learning_messages", AsyncMock(return_value=[None, None, None]))
    monkeypatch.setattr(learner, "_log_learning_context_preview", Mock())
    monkeypatch.setattr(learner_module, "expression_learning_batch_gate", learner_module.ExpressionLearningBatchGate())
    monkeypatch.setattr(learner_module.global_config.expression, "max_expression_learner", 3)
    monkeypatch.setattr(learner_module.global_config.expression, "expression_self_reflect", False)
    monkeypatch.setattr(learner_module.global_config.expression, "use_vector_expression", False)
    monkeypatch.setattr(
        learner_module,
        "prompt_manager",
        SimpleNamespace(
            get_prompt=Mock(return_value=Mock()),
            render_prompt=AsyncMock(return_value="学习提示"),
        ),
    )
    monkeypatch.setattr(
        learner_module.express_learn_model,
        "generate_response_with_context",
        AsyncMock(
            return_value=SimpleNamespace(response="表达候选"),
        ),
    )
    candidates = [("赞同", "确实", "1"), ("开心", "好耶", "2")]
    monkeypatch.setattr(learner_module, "parse_expression_response", lambda _response: (candidates, []))
    monkeypatch.setattr(
        learner,
        "_filter_expressions",
        lambda expressions, _messages: [(situation, style) for situation, style, _source in expressions],
    )

    async def invoke_hook(_name, **kwargs):
        return SimpleNamespace(aborted=False, kwargs=kwargs)

    monkeypatch.setattr(learner, "_get_runtime_manager", lambda: SimpleNamespace(invoke_hook=invoke_hook))
    return learner, sources


def read_expressions(learner_module, engine):
    with Session(engine) as session:
        return session.exec(select(learner_module.Expression).order_by(learner_module.Expression.id)).all()


@pytest.mark.asyncio
@pytest.mark.parametrize("checked", [True, False])
async def test_duplicate_learning_preserves_manual_review_and_runs_one_db_transaction(
    learner_module,
    learner,
    storage,
    checked,
):
    instance, sources = learner
    engine, state = storage
    with Session(engine) as session:
        session.add(
            learner_module.Expression(
                situation="赞同",
                style="确实",
                content_list='["赞同"]',
                count=3,
                session_id="test-session",
                checked=checked,
                modified_by=learner_module.ModifiedBy.USER,
            )
        )
        session.commit()

    loop_thread = threading.get_ident()
    assert await instance._learn_from_session_messages(sources)
    rows = read_expressions(learner_module, engine)
    assert len(rows) == 2
    assert rows[0].count == 4
    assert rows[0].checked is checked
    assert rows[0].modified_by == learner_module.ModifiedBy.USER
    assert rows[1].checked is False
    assert state.threads and len(state.threads) == 1
    assert state.threads[0] != loop_thread
    assert not instance.pending_messages


@pytest.mark.asyncio
@pytest.mark.parametrize("report_contents", [False, True])
async def test_extraction_failure_keeps_sources_for_retry(learner_module, learner, storage, report_contents):
    instance, sources = learner
    engine, state = storage
    generation = learner_module.express_learn_model.generate_response_with_context
    generation.side_effect = RuntimeError("model unavailable")
    if report_contents:
        with pytest.raises(RuntimeError, match="model unavailable"):
            await instance._learn_from_session_messages(sources, learned_contents=[])
    else:
        assert not await instance._learn_from_session_messages(sources)
    assert instance.learning_status == "failed"
    assert instance.pending_messages.snapshot() == sources
    assert not state.threads

    generation.side_effect = None
    assert await instance._learn_from_session_messages(instance.pending_messages.snapshot())
    assert [row.count for row in read_expressions(learner_module, engine)] == [1, 1]
    assert not instance.pending_messages


@pytest.mark.asyncio
async def test_review_error_keeps_whole_batch_without_partial_writes(learner_module, learner, storage, monkeypatch):
    instance, sources = learner
    engine, state = storage
    monkeypatch.setattr(learner_module.global_config.expression, "expression_self_reflect", True)
    review = AsyncMock(side_effect=[(True, "适用", None), (False, "", "review unavailable")])
    monkeypatch.setattr(learner_module, "check_expression_suitability", review)
    log_threads = []
    monkeypatch.setattr(
        learner_module, "append_ai_review_log", lambda **_kwargs: log_threads.append(threading.get_ident())
    )
    with pytest.raises(RuntimeError, match="review unavailable"):
        await instance._learn_from_session_messages(sources, learned_contents=[])
    assert instance.pending_messages.snapshot() == sources
    assert not read_expressions(learner_module, engine)
    assert not state.threads
    assert len(log_threads) == 2
    assert threading.get_ident() not in log_threads


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["no_candidates", "rejected", "no_text"])
async def test_successful_empty_batch_consumes_only_processed_sources(
    learner_module,
    learner,
    storage,
    monkeypatch,
    outcome,
):
    instance, sources = learner
    engine, state = storage
    if outcome == "no_candidates":
        monkeypatch.setattr(learner_module, "parse_expression_response", lambda _response: ([], []))
    elif outcome == "rejected":
        monkeypatch.setattr(learner_module.global_config.expression, "expression_self_reflect", True)
        monkeypatch.setattr(
            learner_module, "check_expression_suitability", AsyncMock(return_value=(False, "不适用", None))
        )
        monkeypatch.setattr(learner_module, "append_ai_review_log", Mock())
    else:
        instance._build_multi_learning_messages.return_value = [None, None]
    new_source = SimpleNamespace(message_id="new-message", session_id="test-session")
    instance.pending_messages.extend([new_source])
    assert not await instance._learn_from_session_messages(sources)
    assert instance.learning_status == "no_results"
    assert instance.pending_messages.snapshot() == [new_source]
    assert not read_expressions(learner_module, engine)
    assert not state.threads


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["second_write", "commit"])
async def test_storage_failure_rolls_back_batch_and_keeps_sources(learner_module, learner, storage, failure):
    instance, sources = learner
    engine, state = storage
    state.failure = failure
    contents = []
    with pytest.raises(RuntimeError, match="failed"):
        await instance._learn_from_session_messages(sources, learned_contents=contents)
    assert instance.pending_messages.snapshot() == sources
    assert not read_expressions(learner_module, engine)
    assert not contents

    state.failure = None
    assert await instance._learn_from_session_messages(instance.pending_messages.snapshot(), learned_contents=contents)
    assert [row.count for row in read_expressions(learner_module, engine)] == [1, 1]
    assert len(contents) == 2
    assert not instance.pending_messages


@pytest.mark.asyncio
async def test_committed_batch_is_consumed_when_index_sync_is_cancelled(learner_module, learner, storage, monkeypatch):
    instance, sources = learner
    engine, _state = storage
    monkeypatch.setattr(instance, "_sync_expression_vector_index_batch", AsyncMock(side_effect=asyncio.CancelledError))
    contents = []
    with pytest.raises(asyncio.CancelledError):
        await instance._learn_from_session_messages(sources, learned_contents=contents)
    assert len(read_expressions(learner_module, engine)) == 2
    assert len(contents) == 2
    assert not instance.pending_messages
