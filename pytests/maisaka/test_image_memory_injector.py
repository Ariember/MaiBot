from types import SimpleNamespace
from unittest.mock import AsyncMock

import asyncio

import pytest

from src.config import image_memory as image_memory_config
from src.config.model_configs import ModelTaskConfig
from src.config.official_configs import AMemorixConfig
from src.maisaka import builtin_tool
from src.maisaka.memory import image_injector as image_injector_module
from src.services.memory_flow_service import ImageMemoryWritebackService


@pytest.fixture
def configured_image_memory(monkeypatch):
    config = AMemorixConfig()
    config.plugin.enabled = True
    config.image_memory.enabled = True
    tasks = ModelTaskConfig()
    tasks.image_embedding.model_list = ["image-model"]
    monkeypatch.setattr(image_memory_config, "global_config", SimpleNamespace(a_memorix=config))
    monkeypatch.setattr(
        image_memory_config.config_manager, "get_model_config", lambda: SimpleNamespace(model_task_config=tasks)
    )
    return config, tasks


@pytest.mark.parametrize(
    "plugin_enabled,image_enabled,task_name,models,expected",
    [
        (False, True, "image_embedding", ["image-model"], False),
        (True, False, "image_embedding", ["image-model"], False),
        (True, True, "image_embedding", [], False),
        (True, True, "image_embedding", [" "], False),
        (True, True, "missing_task", ["image-model"], False),
        (True, True, "image_embedding", ["image-model"], True),
    ],
)
@pytest.mark.asyncio
async def test_image_memory_enablement_controls_injection_tools_and_writeback(
    monkeypatch,
    tmp_path,
    configured_image_memory,
    plugin_enabled,
    image_enabled,
    task_name,
    models,
    expected,
):
    config, tasks = configured_image_memory
    config.plugin.enabled = plugin_enabled
    config.image_memory.enabled = image_enabled
    config.image_memory.task_name = task_name
    tasks.image_embedding.model_list = models
    assert image_memory_config.is_image_memory_enabled() is expected
    assert builtin_tool._get_query_image_memory_tool_spec().enabled is expected
    service = ImageMemoryWritebackService(tmp_path / "jobs.sqlite3")
    assert service._enabled() is expected
    if not expected:
        memory_call = AsyncMock()
        monkeypatch.setattr(image_injector_module.memory_service, "image_memory", memory_call)
        assert (
            await image_injector_module.image_memory_injector.build_injection_message(
                session_id="real-chat",
                source_messages=[SimpleNamespace()],
            )
            == ""
        )
        assert await service._handle_message(SimpleNamespace()) is False
        await service.enqueue(SimpleNamespace())
        assert service._journal is None
        memory_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_image_memory_injector_uses_current_occurrence_and_expands_memory(
    monkeypatch,
    configured_image_memory,
) -> None:
    captured: dict[str, object] = {}
    component = SimpleNamespace(binary_hash="sha256-current")
    message = SimpleNamespace(
        message_id="message-1",
        raw_message=SimpleNamespace(components=[component]),
    )

    monkeypatch.setattr(
        image_injector_module,
        "iter_message_image_components",
        lambda components: iter([("0", components[0])]),
    )

    async def fake_image_memory(*, action: str, **kwargs):
        captured["action"] = action
        captured.update(kwargs)
        # 秒级远程嵌入不应被注入层原有的180毫秒预算提前截断。
        await asyncio.sleep(0.25)
        return {
            "success": True,
            "hits": [
                {
                    "match_kind": "visual_similar",
                    "similarity": 0.91,
                    "observations": [{"text": "照片里是团团"}],
                    "related_memories": [
                        {"target_type": "paragraph", "target_id": "p1", "content": "团团喜欢睡在窗边。"}
                    ],
                }
            ],
        }

    monkeypatch.setattr(image_injector_module.memory_service, "image_memory", fake_image_memory)

    result = await image_injector_module.image_memory_injector.build_injection_message(
        session_id="chat-real",
        source_messages=[message],
    )

    assert "照片里是团团" in result
    assert "团团喜欢睡在窗边" in result
    assert captured["action"] == "search"
    assert "timeout_ms" not in captured
    assert captured["chat_id"] == "chat-real"
    assert captured["content_hash"] == "sha256-current"
    assert captured["current_external_ref"] == "chat:chat-real:message-1:0"


@pytest.mark.asyncio
async def test_image_memory_injector_does_not_hide_service_timeout(monkeypatch, configured_image_memory) -> None:
    component = SimpleNamespace(binary_hash="sha256-current")
    message = SimpleNamespace(message_id="message-1", raw_message=SimpleNamespace(components=[component]))
    monkeypatch.setattr(
        image_injector_module,
        "iter_message_image_components",
        lambda components: iter([("0", components[0])]),
    )

    async def failing_image_memory(**kwargs):
        raise TimeoutError("模型请求超时")

    monkeypatch.setattr(image_injector_module.memory_service, "image_memory", failing_image_memory)
    with pytest.raises(TimeoutError, match="模型请求超时"):
        await image_injector_module.image_memory_injector.build_injection_message(
            session_id="chat-real",
            source_messages=[message],
        )
