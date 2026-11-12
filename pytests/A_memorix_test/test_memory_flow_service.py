import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.A_memorix.core.utils.summary_importer import SUMMARY_PROMPT_TEMPLATE, SummaryImporter
from src.services import memory_flow_service as memory_flow_module


def _fake_global_config(**integration_values):
    return SimpleNamespace(
        a_memorix=SimpleNamespace(
            integration=SimpleNamespace(**integration_values),
        )
    )


def test_person_fact_parse_fact_list_deduplicates_and_filters_short_items():
    raw = '["他喜欢猫", "他喜欢猫", "好", "", "他会弹吉他"]'

    result = memory_flow_module.PersonFactWritebackService._parse_fact_list(raw)

    assert result == ["他喜欢猫", "他会弹吉他"]


@pytest.mark.parametrize("locale", ["zh-CN", "en-US", "ja-JP"])
def test_person_fact_prompt_carries_structured_claim_contract(locale):
    from src.common.prompt_i18n import list_prompt_templates

    rendered = memory_flow_module.load_prompt(
        "a_memorix_person_fact",
        locale=locale,
        person_name="Alice",
        user_evidence_text="[2026-01-10] I moved to Shanghai yesterday.",
        reply_text="Understood.",
    )
    assert "Alice" in rendered
    assert "2026-01-10" in rendered
    assert all(key in rendered for key in ("fact_key", "cardinality", "polarity", "valid_from", "valid_to", "replace"))
    metadata = list_prompt_templates(locale=locale)["a_memorix_person_fact"].metadata
    assert metadata.display_name and metadata.description


@pytest.mark.asyncio
@pytest.mark.parametrize("quote", ["昨天搬到上海了", "并非用户原话"])
async def test_person_fact_change_requires_source_and_keeps_effective_time(monkeypatch, quote):
    import threading

    loop_thread = threading.get_ident()
    user_message = SimpleNamespace(
        message_id="user-move",
        timestamp=200.0,
        processed_plain_text="我昨天搬到上海了。",
    )
    person = SimpleNamespace(person_id="p1", person_name="Alice", is_known=True)
    service = memory_flow_module.PersonFactWritebackService()

    def resolve(message):
        assert threading.get_ident() != loop_thread
        return person

    def collect(message, target):
        assert threading.get_ident() != loop_thread
        return memory_flow_module.PersonFactEvidence([user_message], [])

    service._resolve_target_person = resolve
    service._collect_user_evidence = collect
    service._extract_facts = AsyncMock(
        return_value=[
            {
                "fact": "Alice现居上海。",
                "evidence_message_id": "user-move",
                "evidence_quote": quote,
                "fact_claim": {
                    "fact_key": "residence_city",
                    "cardinality": "single",
                    "polarity": "positive",
                    "change": "replace",
                    "valid_from": 100.0,
                    "valid_to": None,
                },
            }
        ]
    )
    write = AsyncMock()
    monkeypatch.setattr(memory_flow_module, "store_person_memory_from_answer", write)
    trigger = SimpleNamespace(processed_plain_text="我记住了你的新住址。", session_id="chat-1")
    if quote == "并非用户原话":
        with pytest.raises(ValueError, match="原始发言证据"):
            await service._handle_message(trigger)
        write.assert_not_called()
    else:
        await service._handle_message(trigger)
        payload = write.call_args.kwargs
        assert payload["observed_at"] == 200.0
        assert payload["fact_claim"]["valid_from"] == 100.0
        assert payload["fact_claim"]["change"] == "replace"


def test_person_fact_claim_rejects_ambiguous_replacement_and_invalid_range():
    normalize = memory_flow_module.PersonFactWritebackService._normalize_fact_claim
    with pytest.raises(ValueError, match="单值槽位"):
        normalize({"fact_key": "interests", "cardinality": "set", "change": "replace"})
    with pytest.raises(ValueError, match="不能早于"):
        normalize({"fact_key": "residence_city", "valid_from": 200, "valid_to": 100})


def test_person_fact_resolve_target_person_for_private_chat(monkeypatch):
    class FakePerson:
        def __init__(self, person_id: str):
            self.person_id = person_id
            self.is_known = True

    service = memory_flow_module.PersonFactWritebackService.__new__(memory_flow_module.PersonFactWritebackService)
    monkeypatch.setattr(memory_flow_module, "is_bot_self", lambda platform, user_id: False)
    monkeypatch.setattr(memory_flow_module, "get_person_id", lambda platform, user_id: f"{platform}:{user_id}")
    monkeypatch.setattr(memory_flow_module, "Person", FakePerson)

    message = SimpleNamespace(session=SimpleNamespace(platform="qq", user_id="123", group_id=""))

    person = service._resolve_target_person(message)

    assert person is not None
    assert person.person_id == "qq:123"


def test_person_fact_resolve_target_person_for_group_without_reply(monkeypatch):
    class FakePerson:
        def __init__(self, person_id: str):
            self.person_id = person_id
            self.is_known = person_id in {"qq:user-1", "qq:user-2"}

    older_user_message = SimpleNamespace(
        platform="qq",
        user_id="user-1",
        message_info=SimpleNamespace(user_info=SimpleNamespace(user_id="user-1")),
    )
    latest_user_message = SimpleNamespace(
        platform="qq",
        user_id="user-2",
        message_info=SimpleNamespace(user_info=SimpleNamespace(user_id="user-2")),
    )

    def fake_find_messages(**kwargs):
        if kwargs.get("session_id") == "session-1":
            return [older_user_message, latest_user_message]
        return []

    service = memory_flow_module.PersonFactWritebackService.__new__(memory_flow_module.PersonFactWritebackService)
    monkeypatch.setattr(memory_flow_module, "find_messages", fake_find_messages)
    monkeypatch.setattr(memory_flow_module, "is_bot_self", lambda platform, user_id: False)
    monkeypatch.setattr(memory_flow_module, "get_person_id", lambda platform, user_id: f"{platform}:{user_id}")
    monkeypatch.setattr(memory_flow_module, "Person", FakePerson)

    message = SimpleNamespace(
        session_id="session-1",
        timestamp=20.0,
        reply_to="",
        session=SimpleNamespace(platform="qq", user_id="bot-1", group_id="group-1", session_id="session-1"),
    )

    person = service._resolve_target_person(message)

    assert person is not None
    assert person.person_id == "qq:user-2"


def test_person_fact_collect_user_evidence_keeps_latest_target_messages_without_reply(monkeypatch):
    class FakePerson:
        person_id = "qq:user-1"

    def make_message(message_id: str, user_id: str, text: str):
        return SimpleNamespace(
            message_id=message_id,
            platform="qq",
            user_id=user_id,
            processed_plain_text=text,
            message_info=SimpleNamespace(user_info=SimpleNamespace(user_id=user_id)),
        )

    messages = [
        make_message("user-1-a", "user-1", "第一条旧证据"),
        make_message("user-2-a", "user-2", "其他人的插话"),
        make_message("user-1-b", "user-1", "第二条证据"),
        make_message("user-1-c", "user-1", "第三条证据"),
        make_message("user-1-d", "user-1", "第四条最新证据"),
    ]

    def fake_find_messages(**kwargs):
        if kwargs.get("session_id") == "session-1":
            return messages
        return []

    service = memory_flow_module.PersonFactWritebackService.__new__(memory_flow_module.PersonFactWritebackService)
    monkeypatch.setattr(memory_flow_module, "find_messages", fake_find_messages)
    monkeypatch.setattr(memory_flow_module, "is_bot_self", lambda platform, user_id: False)
    monkeypatch.setattr(memory_flow_module, "get_person_id", lambda platform, user_id: f"{platform}:{user_id}")

    message = SimpleNamespace(
        session_id="session-1",
        timestamp=20.0,
        reply_to="",
        session=SimpleNamespace(session_id="session-1"),
    )

    evidence = service._collect_user_evidence(message, FakePerson())

    assert [item.message_id for item in evidence.target_messages] == ["user-1-b", "user-1-c", "user-1-d"]
    assert evidence.context_messages == messages


def test_person_fact_reply_evidence_keeps_context_for_short_answer(monkeypatch):
    class FakePerson:
        person_id = "qq:user-1"

    def make_message(
        *,
        message_id: str,
        user_id: str,
        nickname: str,
        text: str,
        timestamp: float,
    ):
        return SimpleNamespace(
            message_id=message_id,
            platform="qq",
            user_id=user_id,
            timestamp=timestamp,
            processed_plain_text=text,
            message_info=SimpleNamespace(
                user_info=SimpleNamespace(
                    user_id=user_id,
                    user_nickname=nickname,
                    user_cardname="",
                ),
            ),
        )

    bot_question = make_message(
        message_id="bot-question",
        user_id="bot-1",
        nickname="麦麦",
        text="你对什么过敏？",
        timestamp=10.0,
    )
    user_answer = make_message(
        message_id="user-answer",
        user_id="user-1",
        nickname="测试用户",
        text="青霉素。",
        timestamp=11.0,
    )

    def fake_find_messages(**kwargs):
        if kwargs.get("message_id") == "user-answer":
            return [user_answer]
        if kwargs.get("session_id") == "session-1":
            assert kwargs.get("filter_bot") is None
            return [bot_question, user_answer]
        return []

    monkeypatch.setattr(memory_flow_module, "find_messages", fake_find_messages)
    monkeypatch.setattr(memory_flow_module, "is_bot_self", lambda platform, user_id: user_id == "bot-1")
    monkeypatch.setattr(memory_flow_module, "get_person_id", lambda platform, user_id: f"{platform}:{user_id}")

    service = memory_flow_module.PersonFactWritebackService.__new__(memory_flow_module.PersonFactWritebackService)
    reply_message = SimpleNamespace(
        session_id="session-1",
        reply_to="user-answer",
        timestamp=12.0,
        session=SimpleNamespace(session_id="session-1"),
    )

    evidence = service._collect_user_evidence(reply_message, FakePerson())
    evidence_text = service._format_user_evidence(evidence)

    assert evidence.target_messages == [user_answer]
    assert evidence.context_messages == [bot_question, user_answer]
    assert "目标用户原始发言" in evidence_text
    assert "青霉素。" in evidence_text
    assert "邻近上下文" in evidence_text
    assert "麦麦: 你对什么过敏？" in evidence_text


@pytest.mark.asyncio
async def test_person_fact_writeback_skips_bot_only_fact_without_user_evidence(monkeypatch):
    stored_facts: list[tuple[str, str, str]] = []

    class FakePerson:
        person_id = "person-1"
        person_name = "测试用户"
        nickname = "测试用户"
        is_known = True

    service = memory_flow_module.PersonFactWritebackService.__new__(memory_flow_module.PersonFactWritebackService)
    service._resolve_target_person = lambda message: FakePerson()

    async def fake_extract_facts(person, reply_text, user_evidence_text):
        del person, reply_text, user_evidence_text
        return ["测试用户喜欢辣椒"]

    async def fake_store_person_memory_from_answer(person_name: str, memory_content: str, chat_id: str, **kwargs):
        del kwargs
        stored_facts.append((person_name, memory_content, chat_id))

    service._extract_facts = fake_extract_facts
    monkeypatch.setattr(memory_flow_module, "store_person_memory_from_answer", fake_store_person_memory_from_answer)
    monkeypatch.setattr(memory_flow_module, "find_messages", lambda **kwargs: [])

    message = SimpleNamespace(
        processed_plain_text="我记得你喜欢辣椒。",
        session_id="session-1",
        reply_to="",
        session=SimpleNamespace(platform="qq", user_id="bot-1", group_id=""),
    )

    await service._handle_message(message)

    assert stored_facts == []


@pytest.mark.asyncio
async def test_person_fact_writeback_uses_resolved_person_id(monkeypatch):
    stored_payloads: list[dict[str, object]] = []

    class FakePerson:
        person_id = "person-target"
        person_name = "重名用户"
        nickname = "重名用户"
        is_known = True

    user_message = SimpleNamespace(
        message_id="user-1",
        platform="qq",
        user_id="10001",
        processed_plain_text="我长期用青轴键盘。",
        message_info=SimpleNamespace(user_info=SimpleNamespace(user_id="10001")),
    )

    service = memory_flow_module.PersonFactWritebackService()
    service._resolve_target_person = lambda message: FakePerson()

    async def fake_extract_facts(person, reply_text, user_evidence_text):
        assert person.person_id == "person-target"
        assert "我长期用青轴键盘" in user_evidence_text
        del reply_text
        return ["重名用户长期使用青轴键盘"]

    async def fake_store_person_memory_from_answer(person_name: str, memory_content: str, chat_id: str, **kwargs):
        stored_payloads.append(
            {
                "person_name": person_name,
                "memory_content": memory_content,
                "chat_id": chat_id,
                **kwargs,
            }
        )
        return True

    service._extract_facts = fake_extract_facts
    monkeypatch.setattr(memory_flow_module, "store_person_memory_from_answer", fake_store_person_memory_from_answer)
    monkeypatch.setattr(
        memory_flow_module,
        "find_messages",
        lambda **kwargs: [user_message] if kwargs.get("session_id") == "session-1" else [],
    )
    monkeypatch.setattr(memory_flow_module, "is_bot_self", lambda platform, user_id: False)
    monkeypatch.setattr(memory_flow_module, "get_person_id", lambda platform, user_id: "person-target")

    message = SimpleNamespace(
        processed_plain_text="我记住了，你长期用青轴键盘。",
        session_id="session-1",
        reply_to="",
        timestamp=20.0,
        session=SimpleNamespace(platform="qq", user_id="bot-1", group_id="", session_id="session-1"),
    )

    await service._handle_message(message)

    assert len(stored_payloads) == 1
    assert stored_payloads[0]["person_id"] == "person-target"
    assert stored_payloads[0]["evidence_message_ids"] == ["user-1"]


@pytest.mark.asyncio
async def test_person_fact_writeback_marks_verified_user_statement_stable(monkeypatch):
    from src.services import person_fact_verifier

    stored_payloads: list[dict[str, object]] = []
    user_message = SimpleNamespace(
        message_id="user-1",
        platform="qq",
        user_id="10001",
        processed_plain_text="我喜欢猫。",
        message_info=SimpleNamespace(user_info=SimpleNamespace(user_id="10001")),
    )

    class FakePerson:
        person_id = "person-target"
        person_name = "测试用户"
        nickname = "测试用户"
        is_known = True

    service = memory_flow_module.PersonFactWritebackService()
    service._resolve_target_person = lambda message: FakePerson()

    async def fake_extract_facts(person, reply_text, user_evidence_text):
        assert "消息ID: user-1" in user_evidence_text
        return [{"fact": "测试用户喜欢猫。", "evidence_message_id": "user-1", "evidence_quote": "我喜欢猫。"}]

    async def fake_store(person_name, memory_content, chat_id, **kwargs):
        stored_payloads.append(kwargs)
        return True

    service._extract_facts = fake_extract_facts
    monkeypatch.setattr(memory_flow_module, "store_person_memory_from_answer", fake_store)
    monkeypatch.setattr(memory_flow_module, "find_messages", lambda **kwargs: [user_message])
    monkeypatch.setattr(memory_flow_module, "is_bot_self", lambda platform, user_id: False)
    monkeypatch.setattr(memory_flow_module, "get_person_id", lambda platform, user_id: "person-target")
    monkeypatch.setattr(person_fact_verifier, "find_messages", lambda **kwargs: [user_message])
    monkeypatch.setattr(person_fact_verifier, "get_person_id", lambda platform, user_id: "person-target")

    message = SimpleNamespace(
        processed_plain_text="我记住了。",
        session_id="session-1",
        reply_to="",
        timestamp=20.0,
        session=SimpleNamespace(platform="qq", user_id="bot-1", group_id="", session_id="session-1"),
    )
    await service._handle_message(message)

    assert stored_payloads[0]["fact_claim"] == {
        "authority": "direct_user",
        "stability": "stable",
        "profile_section": "stable_facts",
    }
    assert stored_payloads[0]["evidence_message_ids"] == ["user-1"]


@pytest.fixture
def person_fact_window(monkeypatch):
    service = memory_flow_module.PersonFactWritebackService()
    person = SimpleNamespace(person_id="person-1", person_name="Alice", is_known=True)
    trigger = SimpleNamespace(processed_plain_text="我记住了你的喜好。", session_id="chat-1")
    evidence = memory_flow_module.PersonFactEvidence(
        [SimpleNamespace(message_id="user-1", processed_plain_text="我喜欢猫。", timestamp=100.0)],
        [],
    )
    generate = AsyncMock(return_value=SimpleNamespace(response='["Alice喜欢猫。"]'))
    write = AsyncMock(return_value=True)
    service._extractor = SimpleNamespace(generate_response=generate)
    service._resolve_target_person = lambda message: person
    service._collect_user_evidence = lambda message, target: evidence
    monkeypatch.setattr(memory_flow_module, "store_person_memory_from_answer", write)
    return SimpleNamespace(service=service, person=person, trigger=trigger, evidence=evidence, generate=generate, write=write)


@pytest.mark.asyncio
@pytest.mark.parametrize("response", ['["Alice喜欢猫。"]', "[]"])
async def test_person_fact_completed_window_skips_repeated_extraction(person_fact_window, response):
    state = person_fact_window
    state.generate.return_value.response = response
    await state.service._handle_message(state.trigger)
    state.trigger.processed_plain_text = "还有什么其他喜好也可以告诉我。"
    await state.service._handle_message(state.trigger)
    assert state.generate.await_count == 1
    assert state.write.await_count == (0 if response == "[]" else 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("reply_text", ["好的", "收到"])
async def test_person_fact_short_confirmation_keeps_user_fact(person_fact_window, reply_text):
    state = person_fact_window
    state.trigger.processed_plain_text = reply_text
    state.evidence.target_messages[0].processed_plain_text = "我对青霉素过敏。"
    state.generate.return_value.response = '["Alice对青霉素过敏。"]'
    await state.service._handle_message(state.trigger)
    await state.service._handle_message(state.trigger)
    state.generate.assert_awaited_once()
    state.write.assert_awaited_once()
    assert state.write.call_args.args[1] == "Alice对青霉素过敏。"


@pytest.mark.asyncio
async def test_person_fact_same_target_with_new_context_is_extracted_again(person_fact_window):
    state = person_fact_window
    state.evidence.target_messages[0].processed_plain_text = "青霉素。"
    state.generate.return_value.response = "[]"
    await state.service._handle_message(state.trigger)
    state.evidence.context_messages = [
        SimpleNamespace(message_id="question-1", processed_plain_text="你对什么过敏？"),
        *state.evidence.target_messages,
    ]
    state.generate.return_value.response = '["Alice对青霉素过敏。"]'
    await state.service._handle_message(state.trigger)
    await state.service._handle_message(state.trigger)
    assert state.generate.await_count == 2
    state.write.assert_awaited_once()
    assert state.write.call_args.args[1] == "Alice对青霉素过敏。"


@pytest.mark.asyncio
async def test_person_fact_window_is_scoped_and_new_evidence_is_processed(person_fact_window):
    state = person_fact_window
    await state.service._handle_message(state.trigger)
    state.trigger.session_id = "chat-2"
    await state.service._handle_message(state.trigger)
    state.person.person_id = "person-2"
    await state.service._handle_message(state.trigger)
    state.evidence.target_messages.append(
        SimpleNamespace(message_id="user-2", processed_plain_text="我也喜欢狗。", timestamp=200.0)
    )
    await state.service._handle_message(state.trigger)
    state.evidence.target_messages.reverse()
    await state.service._handle_message(state.trigger)
    await state.service._handle_message(state.trigger)
    assert state.generate.await_count == 5
    assert state.write.await_count == 5


@pytest.mark.asyncio
async def test_person_fact_window_with_missing_message_id_is_not_cached(person_fact_window):
    state = person_fact_window
    state.evidence.target_messages.append(
        SimpleNamespace(message_id="", processed_plain_text="我也喜欢狗。", timestamp=200.0)
    )
    await state.service._handle_message(state.trigger)
    await state.service._handle_message(state.trigger)
    assert state.generate.await_count == 2
    assert not state.service._completed_windows


@pytest.mark.asyncio
@pytest.mark.parametrize("response", ["", "不是 JSON", "{}", "[{}]", "[1]", '[""]'])
async def test_person_fact_invalid_output_does_not_complete_window(person_fact_window, response):
    state = person_fact_window
    state.generate.return_value.response = response
    with pytest.raises(ValueError, match="人物事实提取结果"):
        await state.service._handle_message(state.trigger)
    state.generate.return_value.response = "[]"
    await state.service._handle_message(state.trigger)
    await state.service._handle_message(state.trigger)
    assert state.generate.await_count == 2
    state.write.assert_not_awaited()


@pytest.mark.asyncio
async def test_person_fact_model_failure_does_not_complete_window(person_fact_window):
    state = person_fact_window
    state.generate.side_effect = RuntimeError("model unavailable")
    with pytest.raises(RuntimeError, match="model unavailable"):
        await state.service._handle_message(state.trigger)
    state.generate.side_effect = None
    await state.service._handle_message(state.trigger)
    await state.service._handle_message(state.trigger)
    assert state.generate.await_count == 2
    state.write.assert_awaited_once()


@pytest.mark.asyncio
async def test_person_fact_partial_write_failure_does_not_complete_window(person_fact_window):
    state = person_fact_window
    state.generate.return_value.response = '["Alice喜欢猫。", "Alice喜欢狗。"]'
    state.write.side_effect = [True, False, True, True]
    await state.service._handle_message(state.trigger)
    await state.service._handle_message(state.trigger)
    await state.service._handle_message(state.trigger)
    assert state.generate.await_count == 2
    assert state.write.await_count == 4


@pytest.mark.asyncio
async def test_person_fact_completed_windows_are_bounded_and_reset_on_start(person_fact_window):
    state = person_fact_window
    state.generate.return_value.response = "[]"
    for index in range(257):
        state.evidence.target_messages[0].message_id = f"user-{index}"
        await state.service._handle_message(state.trigger)
    assert len(state.service._completed_windows) == 256
    state.evidence.target_messages[0].message_id = "user-0"
    await state.service._handle_message(state.trigger)
    assert state.generate.await_count == 258
    state.service._worker_loop = AsyncMock()
    state.service._historical_reclassify_loop = AsyncMock()
    await state.service.start()
    try:
        assert not state.service._completed_windows
    finally:
        await state.service.shutdown()


@pytest.mark.asyncio
async def test_chat_summary_writeback_service_triggers_when_threshold_reached(monkeypatch):
    events: list[tuple[str, object]] = []

    monkeypatch.setattr(
        memory_flow_module,
        "global_config",
        _fake_global_config(
            chat_summary_writeback_enabled=True,
            chat_summary_writeback_message_threshold=3,
            chat_summary_writeback_context_length=7,
        ),
    )
    monkeypatch.setattr(memory_flow_module, "count_messages", lambda **kwargs: 5)

    async def fake_ingest_summary(**kwargs):
        events.append(("ingest_summary", kwargs))
        return SimpleNamespace(success=True, detail="ok")

    async def fake_load_last_trigger_message_count(self, *, session_id: str, total_message_count: int) -> int:
        del self, session_id, total_message_count
        return 0

    monkeypatch.setattr(memory_flow_module.memory_service, "ingest_summary", fake_ingest_summary)
    monkeypatch.setattr(
        memory_flow_module.ChatSummaryWritebackService,
        "_load_last_trigger_message_count",
        fake_load_last_trigger_message_count,
    )

    service = memory_flow_module.ChatSummaryWritebackService()
    message = SimpleNamespace(session_id="session-1", session=SimpleNamespace(user_id="user-1", group_id="group-1"))

    await service._handle_message(message)

    assert len(events) == 1
    _, payload = events[0]
    assert payload["external_id"] == "chat_auto_summary:session-1:5"
    assert payload["chat_id"] == "session-1"
    assert payload["text"] == ""
    assert payload["metadata"]["generate_from_chat"] is True
    assert payload["metadata"]["context_length"] == 5
    assert payload["metadata"]["configured_context_length"] == 7
    assert payload["metadata"]["previous_trigger_message_count"] == 0
    assert payload["metadata"]["pending_message_count"] == 5
    assert payload["metadata"]["trigger"] == "message_threshold"
    assert payload["user_id"] == "user-1"
    assert payload["group_id"] == "group-1"


@pytest.mark.asyncio
async def test_chat_summary_writeback_service_skips_when_threshold_not_reached(monkeypatch):
    called = False

    monkeypatch.setattr(
        memory_flow_module,
        "global_config",
        _fake_global_config(
            chat_summary_writeback_enabled=True,
            chat_summary_writeback_message_threshold=6,
            chat_summary_writeback_context_length=9,
        ),
    )
    monkeypatch.setattr(memory_flow_module, "count_messages", lambda **kwargs: 5)

    async def fake_ingest_summary(**kwargs):
        nonlocal called
        called = True
        return SimpleNamespace(success=True, detail="ok")

    async def fake_load_last_trigger_message_count(self, *, session_id: str, total_message_count: int) -> int:
        del self, session_id, total_message_count
        return 0

    monkeypatch.setattr(memory_flow_module.memory_service, "ingest_summary", fake_ingest_summary)
    monkeypatch.setattr(
        memory_flow_module.ChatSummaryWritebackService,
        "_load_last_trigger_message_count",
        fake_load_last_trigger_message_count,
    )

    service = memory_flow_module.ChatSummaryWritebackService()
    message = SimpleNamespace(session_id="session-1", session=SimpleNamespace(user_id="user-1", group_id="group-1"))

    await service._handle_message(message)

    assert called is False


@pytest.mark.asyncio
async def test_chat_summary_writeback_service_restores_previous_trigger_count(monkeypatch):
    events: list[tuple[str, object]] = []

    monkeypatch.setattr(
        memory_flow_module,
        "global_config",
        _fake_global_config(
            chat_summary_writeback_enabled=True,
            chat_summary_writeback_message_threshold=3,
            chat_summary_writeback_context_length=7,
        ),
    )
    monkeypatch.setattr(memory_flow_module, "count_messages", lambda **kwargs: 8)

    async def fake_ingest_summary(**kwargs):
        events.append(("ingest_summary", kwargs))
        return SimpleNamespace(success=True, detail="ok")

    async def fake_load_last_trigger_message_count(self, *, session_id: str, total_message_count: int) -> int:
        del self, session_id, total_message_count
        return 5

    monkeypatch.setattr(memory_flow_module.memory_service, "ingest_summary", fake_ingest_summary)
    monkeypatch.setattr(
        memory_flow_module.ChatSummaryWritebackService,
        "_load_last_trigger_message_count",
        fake_load_last_trigger_message_count,
    )

    service = memory_flow_module.ChatSummaryWritebackService()
    message = SimpleNamespace(session_id="session-1", session=SimpleNamespace(user_id="user-1", group_id="group-1"))

    await service._handle_message(message)

    assert len(events) == 1
    _, payload = events[0]
    assert payload["external_id"] == "chat_auto_summary:session-1:8"
    assert service._states["session-1"].last_trigger_message_count == 8


def test_chat_summary_writeback_effective_context_length_uses_pending_window():
    assert (
        memory_flow_module.ChatSummaryWritebackService._effective_context_length(
            configured_context_length=50,
            pending_message_count=12,
        )
        == 12
    )
    assert (
        memory_flow_module.ChatSummaryWritebackService._effective_context_length(
            configured_context_length=8,
            pending_message_count=12,
        )
        == 8
    )


def test_chat_summary_writeback_counts_until_trigger_message(monkeypatch):
    calls: list[dict[str, object]] = []

    def fake_count_messages(**kwargs):
        calls.append(kwargs)
        return 12

    monkeypatch.setattr(memory_flow_module, "count_messages", fake_count_messages)

    assert (
        memory_flow_module.ChatSummaryWritebackService._count_messages_until_trigger(
            session_id="session-1",
            message_time=123.45,
        )
        == 12
    )
    assert calls == [{"session_id": "session-1", "end_time": 123.45}]


def test_summary_prompt_keeps_static_rules_before_chat_history():
    prompt = SUMMARY_PROMPT_TEMPLATE.format(
        bot_name="测试机器人",
        personality_context="你的性格设定是：稳定。",
        identity_catalog="[{id:1}]",
        previous_summary_context="上轮动态摘要",
        chat_history="用户：第一条动态消息",
        image_evidence_catalog="无",
    )

    rules_index = prompt.index("先筛选")
    chat_history_index = prompt.index("本轮聊天")
    dynamic_history_index = prompt.index("用户：第一条动态消息")

    assert rules_index < chat_history_index < dynamic_history_index
    assert rules_index < prompt.index("上轮动态摘要")
    assert rules_index < prompt.index("你的性格设定是：稳定。")
    assert rules_index < prompt.index("[{id:1}]")


def test_summary_prompt_forbids_repeating_rejected_fact_values():
    prompt = SUMMARY_PROMPT_TEMPLATE.format(
        bot_name="测试机器人",
        personality_context="你的性格设定是：稳定。",
        identity_catalog="[]",
        previous_summary_context="",
        chat_history="用户：不是猫毛，是青霉素",
        image_evidence_catalog="无",
    )

    assert "更正只写最终新状态" in prompt
    assert "不复述错误旧值和纠错过程" in prompt
    assert "不复述其具体值" in prompt


def test_summary_review_cleaner_does_not_guess_validity_from_keywords():
    dirty_summary = "此前记录林遥对花生过敏，这是测试示例，后来已纠正。"

    assert SummaryImporter._clean_review_summary(dirty_summary) == dirty_summary


@pytest.mark.asyncio
async def test_chat_summary_writeback_service_falls_back_to_current_count_for_legacy_summary(monkeypatch):
    called = False

    monkeypatch.setattr(
        memory_flow_module,
        "global_config",
        _fake_global_config(
            chat_summary_writeback_enabled=True,
            chat_summary_writeback_message_threshold=3,
            chat_summary_writeback_context_length=7,
        ),
    )
    monkeypatch.setattr(memory_flow_module, "count_messages", lambda **kwargs: 5)

    async def fake_ingest_summary(**kwargs):
        nonlocal called
        called = True
        return SimpleNamespace(success=True, detail="ok")

    async def fake_load_last_trigger_message_count(self, *, session_id: str, total_message_count: int) -> int:
        del self, session_id, total_message_count
        return 5

    monkeypatch.setattr(memory_flow_module.memory_service, "ingest_summary", fake_ingest_summary)
    monkeypatch.setattr(
        memory_flow_module.ChatSummaryWritebackService,
        "_load_last_trigger_message_count",
        fake_load_last_trigger_message_count,
    )

    service = memory_flow_module.ChatSummaryWritebackService()
    message = SimpleNamespace(session_id="session-1", session=SimpleNamespace(user_id="user-1", group_id="group-1"))

    await service._handle_message(message)

    assert called is False
    assert service._states["session-1"].last_trigger_message_count == 5


@pytest.mark.asyncio
async def test_chat_summary_writeback_service_loads_trigger_count_from_summary_metadata(monkeypatch):
    class FakeMetadataStore:
        @staticmethod
        def get_summary_checkpoint_count(chat_id: str) -> int:
            return 0

        @staticmethod
        def get_paragraphs_by_source(source: str):
            assert source == "chat_summary:session-1"
            return [
                {"created_at": 1.0, "metadata": {"trigger_message_count": 3}},
                {"created_at": 2.0, "metadata": {"trigger_message_count": 6}},
            ]

    class FakeRuntimeManager:
        @staticmethod
        async def _ensure_kernel():
            return SimpleNamespace(metadata_store=FakeMetadataStore())

    monkeypatch.setattr(memory_flow_module.memory_service_module, "a_memorix_host_service", FakeRuntimeManager())

    service = memory_flow_module.ChatSummaryWritebackService()

    restored = await service._load_last_trigger_message_count(session_id="session-1", total_message_count=8)

    assert restored == 6


@pytest.mark.asyncio
async def test_memory_automation_service_auto_starts_and_delegates(monkeypatch):
    from unittest.mock import AsyncMock

    monkeypatch.setattr(memory_flow_module.ImageMemoryWritebackService, 'start', AsyncMock())
    monkeypatch.setattr(memory_flow_module.ImageMemoryWritebackService, 'shutdown', AsyncMock())
    observe_identity = AsyncMock()
    monkeypatch.setattr(memory_flow_module.MemoryAutomationService, "_observe_sender_identity", observe_identity)
    events: list[tuple[str, str]] = []

    class FakeFactWriteback:
        async def start(self):
            events.append(("start", "fact"))

        async def enqueue(self, message):
            events.append(("sent", message.session_id))

        async def shutdown(self):
            events.append(("shutdown", "fact"))

    class FakeChatSummaryWriteback:
        async def start(self):
            events.append(("start", "summary"))

        async def enqueue(self, message):
            events.append(("summary", message.session_id))

        async def shutdown(self):
            events.append(("shutdown", "summary"))

    service = memory_flow_module.MemoryAutomationService()
    service.fact_writeback = FakeFactWriteback()
    service.chat_summary_writeback = FakeChatSummaryWriteback()

    await service.on_message_sent(SimpleNamespace(session_id="session-1"))
    await service.shutdown()

    observe_identity.assert_awaited_once()
    assert events == [
        ("start", "fact"),
        ("start", "summary"),
        ("sent", "session-1"),
        ("summary", "session-1"),
        ("shutdown", "summary"),
        ("shutdown", "fact"),
    ]


@pytest.mark.asyncio
async def test_memory_automation_service_on_incoming_message_auto_starts_only(monkeypatch):
    from unittest.mock import AsyncMock

    monkeypatch.setattr(memory_flow_module.ImageMemoryWritebackService, 'start', AsyncMock())
    monkeypatch.setattr(memory_flow_module.ImageMemoryWritebackService, 'enqueue', AsyncMock())
    monkeypatch.setattr(memory_flow_module.ImageMemoryWritebackService, 'shutdown', AsyncMock())
    observe_identity = AsyncMock()
    monkeypatch.setattr(memory_flow_module.MemoryAutomationService, "_observe_sender_identity", observe_identity)
    events: list[tuple[str, str]] = []

    class FakeFactWriteback:
        async def start(self):
            events.append(("start", "fact"))

        async def enqueue(self, message):
            events.append(("sent", message.session_id))

        async def shutdown(self):
            events.append(("shutdown", "fact"))

    class FakeChatSummaryWriteback:
        async def start(self):
            events.append(("start", "summary"))

        async def enqueue(self, message):
            events.append(("summary", message.session_id))

        async def shutdown(self):
            events.append(("shutdown", "summary"))

    service = memory_flow_module.MemoryAutomationService()
    service.fact_writeback = FakeFactWriteback()
    service.chat_summary_writeback = FakeChatSummaryWriteback()

    await service.on_incoming_message(SimpleNamespace(session_id="session-1"))
    await service.shutdown()

    observe_identity.assert_awaited_once()
    assert events == [
        ("start", "fact"),
        ("start", "summary"),
        ("shutdown", "summary"),
        ("shutdown", "fact"),
    ]


def test_chat_summary_writeback_metadata_decodes_json_bytes_only():
    metadata = memory_flow_module.ChatSummaryWritebackService._paragraph_metadata(
        {"metadata": json.dumps({"trigger_message_count": 7}).encode("utf-8")}
    )
    invalid = memory_flow_module.ChatSummaryWritebackService._paragraph_metadata({"metadata": b"not-json-or-utf8"})

    assert metadata == {"trigger_message_count": 7}
    assert invalid == {}
