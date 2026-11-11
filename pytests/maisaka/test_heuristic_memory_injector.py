from threading import get_ident
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.maisaka.memory import heuristic_injector
from src.services.memory_service import MemoryHit


@pytest.mark.asyncio
async def test_heuristic_recall_reads_messages_outside_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    loop_thread = get_ident()
    reads = []
    session = SimpleNamespace(session_id="chat-real")
    message = SimpleNamespace(platform="", message_info=SimpleNamespace(user_info=SimpleNamespace(user_id="")))
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
    injector = heuristic_injector.HeuristicMemoryInjector()
    monkeypatch.setattr(injector, "_build_chat_impression", AsyncMock(return_value="旅行"))
    monkeypatch.setattr(
        injector, "_search_related_memory", AsyncMock(return_value=[MemoryHit(content="上周去了杭州。")])
    )

    result = await injector.build_injection_message(session_id=session.session_id)

    assert "上周去了杭州" in result
    assert reads == ["count", "find"]
