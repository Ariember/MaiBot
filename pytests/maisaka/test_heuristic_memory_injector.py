from threading import get_ident
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.maisaka.memory import heuristic_injector
from src.services.llm_service import LLMServiceClient
from src.services.memory_service import MemoryHit


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["想再去杭州旅行", " \r\n "])
async def test_heuristic_recall_uses_messages_without_generation(
    monkeypatch: pytest.MonkeyPatch, text: str,
) -> None:
    loop_thread = get_ident()
    reads = []
    session = SimpleNamespace(session_id="chat-real")
    message = SimpleNamespace(
        platform="", processed_plain_text=text,
        message_info=SimpleNamespace(user_info=SimpleNamespace(user_id="", user_nickname="小明")),
    )
    config = SimpleNamespace(
        heuristic_memory_recall_enabled=True,
        heuristic_memory_recall_window_size=1,
        heuristic_memory_recall_cache_ttl_seconds=0,
        heuristic_memory_recall_min_interval_seconds=0,
        heuristic_memory_recall_min_new_messages=1,
        heuristic_memory_recall_max_chars=900,
    )
    monkeypatch.setattr(
        heuristic_injector, "global_config", SimpleNamespace(a_memorix=SimpleNamespace(integration=config))
    )
    monkeypatch.setattr(heuristic_injector.chat_manager, "get_existing_session_by_session_id", lambda _: session)

    def count(**kwargs):
        assert get_ident() != loop_thread
        assert kwargs["session_id"] == session.session_id
        reads.append("count")
        return 1

    def find(**kwargs):
        assert get_ident() != loop_thread
        assert kwargs["session_id"] == session.session_id
        reads.append("find")
        return [message]

    monkeypatch.setattr(heuristic_injector, "count_messages", count)
    monkeypatch.setattr(heuristic_injector, "find_messages", find)
    generate = AsyncMock(side_effect=AssertionError("普通召回不应生成聊天印象"))
    monkeypatch.setattr(LLMServiceClient, "generate_response", generate)
    injector = heuristic_injector.HeuristicMemoryInjector()
    search = AsyncMock(return_value=[MemoryHit(content="上周去了杭州。")])
    monkeypatch.setattr(injector, "_search_related_memory", search)

    result = await injector.build_injection_message(session_id=session.session_id)

    if text.strip():
        assert "上周去了杭州" in result
        search.assert_awaited_once()
        assert search.await_args.args[0] == "- 小明: 想再去杭州旅行"
    else:
        assert result == ""
        search.assert_not_awaited()
    generate.assert_not_awaited()
    assert reads == ["count", "find"]


def test_recall_query_keeps_latest_messages_within_budget() -> None:
    messages = [
        SimpleNamespace(
            processed_plain_text=f"话题{index:02d}：" + "旅行" * 200,
            message_info=SimpleNamespace(user_info=SimpleNamespace(user_nickname="小明")),
        )
        for index in range(20)
    ]

    query = heuristic_injector.HeuristicMemoryInjector._build_recall_query(messages)

    assert len(query) <= 1000
    assert "话题00" not in query
    assert query.index("话题18") < query.index("话题19")
    assert query.splitlines()[-1].startswith("- 小明: 话题19：")
    assert query.endswith("...")


def test_recall_query_skips_blank_messages_and_normalizes_lines() -> None:
    user_info = SimpleNamespace(user_nickname="小明")
    messages = [
        SimpleNamespace(processed_plain_text=text, message_info=SimpleNamespace(user_info=user_info))
        for text in [" 旧话题 ", "\r\n", "杭州\n旅行"]
    ]

    assert heuristic_injector.HeuristicMemoryInjector._build_recall_query(messages) == "- 小明: 旧话题\n- 小明: 杭州 旅行"
