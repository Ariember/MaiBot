from io import BytesIO
from typing import Tuple
from types import SimpleNamespace
from unittest.mock import AsyncMock

from PIL import Image
from pydantic import ValidationError

import base64
import pytest
import threading

from src.config.model_configs import ModelInfo
from src.llm_models.image_normalizer import normalize_context_images, normalize_image_part
from src.llm_models.payload_content.context_item import (
    AssistantMessageItem,
    ContextImagePart,
    ContextItemMeta,
    ContextTextPart,
    ProviderReplayFragment,
    ProviderScope,
    UserMessageItem,
)


def picture(size: Tuple[int, int], color: str = "red") -> ContextImagePart:
    output = BytesIO()
    Image.new("RGB", size, color).save(output, format="PNG")
    return ContextImagePart("png", base64.b64encode(output.getvalue()).decode("ascii"))


@pytest.mark.parametrize("size", [(10, 20), (600, 400), (20, 2000), (2000, 20), (1, 2000)])
def test_resizing_and_splitting_obey_both_dimensions(size: Tuple[int, int]) -> None:
    parts = normalize_image_part(picture(size), max_side=100, min_side=32)
    assert 1 <= len(parts) <= 16
    for part in parts:
        with Image.open(BytesIO(base64.b64decode(part.image_base64))) as image:
            assert min(image.size) >= 32
            assert max(image.size) <= 100


def test_compliant_picture_preserves_original_bytes() -> None:
    part = picture((60, 80))
    assert normalize_image_part(part, max_side=100, min_side=32)[0] is part


def test_request_limit_keeps_recent_images_and_history_immutable() -> None:
    older = picture((10, 10), "red")
    newer = picture((10, 10), "blue")
    first = UserMessageItem(ContextItemMeta.create(), (older,))
    last = AssistantMessageItem(ContextItemMeta.create(), (ContextTextPart("描述"), newer))
    result = normalize_context_images([first, last], max_images=1)
    assert result[0].parts == (ContextTextPart("[图片因模型数量限制已省略]"),)
    assert result[1] is last
    assert result[0].meta is first.meta
    assert first.parts == (older,)


def test_limit_counts_generated_slices_and_retains_the_last_ones() -> None:
    original = picture((20, 2000))
    item = UserMessageItem(ContextItemMeta.create(), (original,))
    slices = normalize_image_part(original, max_side=100)
    result = normalize_context_images([item], max_images=2, max_side=100)
    images = [part for part in result[0].parts if isinstance(part, ContextImagePart)]
    assert images == slices[-2:]
    assert len(result[0].parts) == len(slices)
    assert item.parts == (original,)


@pytest.mark.parametrize("max_images,max_side", [(1, 8000), (0, 8)])
def test_changed_assistant_images_invalidate_provider_replay(max_images: int, max_side: int) -> None:
    replay = ProviderReplayFragment.from_payload(
        ProviderScope(1, "openai", "provider", "endpoint", "model"), {"content": "original"}
    )
    original = AssistantMessageItem(
        ContextItemMeta.create(), (picture((10, 10)), picture((10, 10), "blue")), replay=replay
    )
    result = normalize_context_images([original], max_images=max_images, max_side=max_side)
    assert result[0].replay is None
    assert original.replay is replay


def test_one_pixel_maximum_terminates_splitting() -> None:
    parts = normalize_image_part(picture((1, 30)), max_side=1)
    assert len(parts) == 16


def test_palette_transparency_survives_padding() -> None:
    output = BytesIO()
    image = Image.new("P", (2, 80), 0)
    image.putpalette([255, 0, 0, 0, 0, 255] + [0] * 762)
    image.save(output, format="PNG", transparency=0)
    part = ContextImagePart("png", base64.b64encode(output.getvalue()).decode("ascii"))
    result = normalize_image_part(part, max_side=100, min_side=32)
    with Image.open(BytesIO(base64.b64decode(result[0].image_base64))) as padded:
        assert padded.size == (32, 100)
        assert padded.convert("RGBA").getpixel((0, 0))[3] == 0


def test_gif_is_unchanged_when_compliant_and_uses_first_frame_when_resized() -> None:
    output = BytesIO()
    Image.new("RGB", (20, 20), "red").save(
        output, format="GIF", save_all=True, append_images=[Image.new("RGB", (20, 20), "blue")], duration=100,
    )
    part = ContextImagePart("gif", base64.b64encode(output.getvalue()).decode("ascii"))
    assert normalize_image_part(part)[0] is part
    normalized = normalize_image_part(part, max_side=10)[0]
    assert normalized.image_format == "png"
    with Image.open(BytesIO(base64.b64decode(normalized.image_base64))) as resized:
        assert resized.size == (10, 10)
        assert resized.convert("RGB").getpixel((0, 0)) == (255, 0, 0)


@pytest.mark.parametrize("limits", [{"max_images": -1}, {"image_min_side": 0}, {"image_max_side": 16, "image_min_side": 32}])
def test_invalid_model_limits_are_rejected(limits) -> None:
    with pytest.raises(ValidationError):
        ModelInfo(model_identifier="vision", name="vision", api_provider="provider", model_type="llm", **limits)


def test_snapshot_round_trip_preserves_limits_and_older_snapshot_uses_defaults() -> None:
    from src.llm_models.model_client import ensure_configured_clients_loaded
    from src.llm_models.request_snapshot import deserialize_model_info_snapshot, serialize_model_info_snapshot

    ensure_configured_clients_loaded()
    model = ModelInfo(
        model_identifier="vision", name="vision", api_provider="provider", model_type="llm",
        max_images=3, image_max_side=2048, image_min_side=32,
    )
    snapshot = serialize_model_info_snapshot(model)
    restored = deserialize_model_info_snapshot(snapshot)
    assert (restored.max_images, restored.image_max_side, restored.image_min_side) == (3, 2048, 32)
    for field in ("max_images", "image_max_side", "image_min_side"):
        del snapshot[field]
    restored = deserialize_model_info_snapshot(snapshot)
    assert (restored.max_images, restored.image_max_side, restored.image_min_side) == (0, 8000, 1)


def test_invalid_request_limits_are_exposed() -> None:
    with pytest.raises(ValueError, match="图片限制"):
        normalize_context_images([], max_side=100, min_side=101)


@pytest.mark.asyncio
async def test_request_uses_selected_models_image_limits(monkeypatch) -> None:
    from src.llm_models import utils_model

    model = ModelInfo(
        model_identifier="vision", name="vision", api_provider="provider", model_type="llm",
        max_images=1, image_max_side=50, image_min_side=32,
    )
    orchestrator = utils_model.LLMOrchestrator("utils", "test.image_limits")
    monkeypatch.setattr(orchestrator, "_select_model", AsyncMock(return_value=(model, object(), object())))
    monkeypatch.setattr(orchestrator, "_adjust_model_usage", lambda *args, **kwargs: None)
    monkeypatch.setattr(orchestrator, "_build_client_request", lambda **kwargs: kwargs)
    request_mock = AsyncMock(return_value=utils_model.APIResponse())
    monkeypatch.setattr(orchestrator, "_attempt_request_on_model_with_timeout", request_mock)
    item = UserMessageItem(ContextItemMeta.create(), (picture((80, 80)), picture((10, 10), "blue")))

    await orchestrator._execute_request(
        utils_model.RequestType.RESPONSE, context_factory=lambda _: [item], model_name=model.name,
    )
    sent = request_mock.call_args.args[2]["context_items"][0]
    assert isinstance(sent.parts[0], ContextTextPart)
    with Image.open(BytesIO(base64.b64decode(sent.parts[1].image_base64))) as image:
        assert image.size == (32, 32)
        assert image.getpixel((0, 0)) == (0, 0, 255)
    assert all(isinstance(part, ContextImagePart) for part in item.parts)


@pytest.mark.asyncio
@pytest.mark.parametrize("error_code,error_message", [(413, "too large"), (400, "Exceeded limit on max bytes per data-uri item: 2048")])
async def test_compression_retry_preserves_limits_off_event_loop(monkeypatch, error_code, error_message) -> None:
    from src.llm_models import utils_model

    model = ModelInfo(
        model_identifier="vision", name="vision", api_provider="provider", model_type="llm",
        max_images=1, image_max_side=100, image_min_side=32,
    )
    provider = utils_model.APIProvider(name="provider", base_url="https://example.com", api_key="test", max_retry=1)
    original = UserMessageItem(ContextItemMeta.create(), (picture((80, 80)),))
    request = utils_model.ResponseRequest(model_info=model, context_items=[original])
    orchestrator = utils_model.LLMOrchestrator("utils", "test.image_limits")
    client = SimpleNamespace(get_response=AsyncMock(side_effect=[
        utils_model.RespNotOkException(error_code, error_message), utils_model.APIResponse(),
    ]))
    main_thread = threading.get_ident()
    compressed_threads = []
    normalized_threads = []

    def compress(items, img_target_size):
        compressed_threads.append(threading.get_ident())
        assert items == [original]
        assert img_target_size > 0
        return [UserMessageItem(original.meta, (picture((8, 8)),))]

    def normalize(*args, **kwargs):
        normalized_threads.append(threading.get_ident())
        return normalize_context_images(*args, **kwargs)

    monkeypatch.setattr(utils_model, "compress_messages", compress)
    monkeypatch.setattr(utils_model, "normalize_context_images", normalize)
    monkeypatch.setattr(utils_model, "has_request_snapshot", lambda _: True)
    monkeypatch.setattr(utils_model, "update_failed_request_attempt", lambda *args, **kwargs: None)
    monkeypatch.setattr(utils_model, "mark_request_succeeded", lambda *args: None)
    await orchestrator._attempt_request_on_model(provider, client, request)

    assert client.get_response.await_count == 2
    assert len(compressed_threads) == len(normalized_threads) == 1
    assert compressed_threads[0] == normalized_threads[0] != main_thread
    retry = client.get_response.call_args.args[0]
    with Image.open(BytesIO(base64.b64decode(retry.context_items[0].parts[0].image_base64))) as image:
        assert image.size == (32, 32)
    assert request.context_items == [original]
