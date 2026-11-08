from io import BytesIO
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

import base64
import pytest

from src.common.data_models.message_component_data_model import (
    EmojiComponent,
    ForwardComponent,
    ForwardNodeComponent,
    ImageComponent,
)
from src.emoji_system import image_gallery as gallery
from src.emoji_system.image_library import ImageLibrary
from src.common.database.database_model import Images, ImageType
from src.maisaka.builtin_tool import search_images
from src.prompt.prompt_manager import PromptManager


@pytest.fixture(autouse=True)
def prompts(monkeypatch):
    manager = PromptManager()
    manager.load_prompts()
    monkeypatch.setattr(gallery, "prompt_manager", manager)


@pytest.fixture
def library(tmp_path, monkeypatch):
    instance = ImageLibrary(tmp_path, 1024 * 1024, 100)
    monkeypatch.setattr(gallery, "get_image_library", lambda: instance)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Images.__table__.create(engine)

    @contextmanager
    def session():
        with Session(engine) as db:
            yield db
            db.commit()

    monkeypatch.setattr(gallery, "get_db_session", session)
    yield instance
    engine.dispose()


@pytest.fixture
def png():
    stream = BytesIO()
    Image.new("RGB", (4, 4), "red").save(stream, "PNG")
    return stream.getvalue()


def test_caption_preview_preserves_transparent_background(library):
    stream = BytesIO()
    Image.new("RGBA", (8, 8), (0, 0, 0, 0)).save(stream, "PNG")
    original = stream.getvalue()
    item, _ = library.add_bytes(original, "transparent.png")
    preview = base64.b64decode(gallery._caption_image(library, item["id"]))
    with Image.open(BytesIO(preview)) as image:
        assert image.getpixel((0, 0)) == (255, 255, 255)
    assert library.read_bytes(item["id"]) == original


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "enabled,mode,groups,group_id,count",
    [
        (False, "whitelist", [], None, 0),
        (True, "whitelist", [], None, 1),
        (True, "whitelist", [], "123", 0),
        (True, "whitelist", ["123"], "123", 1),
        (True, "blacklist", ["123"], "123", 0),
        (True, "blacklist", [], "123", 1),
    ],
)
async def test_receive_nested_images_obeys_collection_rules(
    library, png, monkeypatch, enabled, mode, groups, group_id, count
):
    monkeypatch.setattr(
        gallery,
        "global_config",
        SimpleNamespace(
            emoji=SimpleNamespace(
                collect_images=enabled,
                image_collection_mode=mode,
                image_collection_groups=groups,
            )
        ),
    )
    component = EmojiComponent(binary_hash="", binary_data=png)
    forward = ForwardNodeComponent([ForwardComponent(user_nickname="人", message_id="msg", content=[component])])
    message = SimpleNamespace(
        message_info=SimpleNamespace(group_info=SimpleNamespace(group_id=group_id) if group_id else None),
        raw_message=SimpleNamespace(components=[forward]),
    )
    await gallery.collect_message_images(message)
    assert len(library.list_items()) == count
    if count:
        assert library.list_items()[0]["tags"] == ["表情包"]
        assert library.read_bytes(library.list_items()[0]["id"]) == png
    assert component.binary_data == png


@pytest.mark.asyncio
async def test_collection_limits_work_and_continues_after_invalid_image(library, png, monkeypatch):
    monkeypatch.setattr(gallery, "global_config", SimpleNamespace(emoji=SimpleNamespace(collect_images=True)))
    calls = []

    def add(data, filename, tags):
        calls.append(data)
        if data == b"invalid":
            raise ValueError("无效图片")

    monkeypatch.setattr(library, "add_bytes", add)
    message = SimpleNamespace(
        message_info=SimpleNamespace(group_info=None),
        raw_message=SimpleNamespace(
            components=[
                ImageComponent(binary_hash="", binary_data=b"invalid"),
                *[ImageComponent(binary_hash="", binary_data=png) for _ in range(25)],
            ]
        ),
    )
    await gallery.collect_message_images(message)
    assert len(calls) == 24 and calls[-1] == png


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response,status", [('```json\n{"tags":["表情包","开心"]}\n```', "done"), ('{"tags":[]}', "failed")]
)
async def test_caption_keeps_manual_tags_and_records_failures(library, png, monkeypatch, response, status):
    item, _ = library.add_bytes(png, "test.png", ["手动"])
    model = AsyncMock(return_value=SimpleNamespace(response=response))
    monkeypatch.setattr(
        gallery, "LLMServiceClient", lambda **kwargs: SimpleNamespace(generate_response_for_image=model)
    )
    await gallery.caption_library_image(item["id"])
    updated = library.get(item["id"])
    assert updated["manual_tags"] == ["手动"]
    assert updated["caption_status"] == status
    if status == "done":
        assert updated["auto_tags"] == ["表情包", "开心"]
    assert model.call_args.args[2] == "jpeg"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response,query,found",
    [
        ('{"id":null}', "开心", False),
        ('{"id":"unknown"}', "开心", True),
        ("invalid", "不存在的猫咪", False),
    ],
)
async def test_search_rejects_unknown_ids_and_never_sends_random_images(
    library, png, monkeypatch, response, query, found
):
    library.add_bytes(png, "test.png", ["开心"])
    monkeypatch.setattr(
        gallery,
        "LLMServiceClient",
        lambda **kwargs: SimpleNamespace(
            generate_response=AsyncMock(return_value=SimpleNamespace(response=response)),
        ),
    )
    result = await gallery.select_library_image(query, session_id="real-session")
    assert bool(result) == found


@pytest.mark.asyncio
async def test_search_accepts_semantic_match_and_passes_real_session(library, png, monkeypatch):
    item, _ = library.add_bytes(png, "test.png", ["高兴"])
    model = AsyncMock(return_value=SimpleNamespace(response='{"id":"' + item["id"] + '"}'))
    monkeypatch.setattr(gallery, "LLMServiceClient", lambda **kwargs: SimpleNamespace(generate_response=model))
    assert (await gallery.select_library_image("喜悦", session_id="real-session"))["id"] == item["id"]
    assert model.call_args.kwargs["session_id"] == "real-session"


@pytest.mark.asyncio
async def test_search_excludes_banned_native_emoji(library, png, monkeypatch):
    item, _ = library.add_bytes(png, "开心.png", ["开心"])
    with gallery.get_db_session() as session:
        session.add(
            Images(
                image_hash=item["id"],
                description="开心",
                full_path="emoji.png",
                image_type=ImageType.EMOJI,
                is_banned=True,
            )
        )
    model = AsyncMock()
    monkeypatch.setattr(gallery, "LLMServiceClient", model)
    assert await gallery.select_library_image("开心") is None
    model.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("is_emoji", [False, True])
@pytest.mark.parametrize("target_id,sent", [("post:123", True), ("post:123", False), ("unknown", True), ("", True)])
async def test_search_tool_sends_original_bytes_to_existing_stream(
    library, png, monkeypatch, target_id, sent, is_emoji
):
    item, _ = library.add_bytes(png, "test.png", ["表情包"] if is_emoji else ["开心"])
    target = object()
    ctx = SimpleNamespace(
        runtime=SimpleNamespace(
            session_id="real-session",
            chat_stream=SimpleNamespace(platform="xiaoheihe"),
            find_source_message_by_id=lambda value: target if value == "post:123" else None,
        ),
        build_failure_result=lambda *args, **kwargs: {"success": False},
        build_success_result=lambda *args, **kwargs: {"success": True},
    )
    monkeypatch.setattr(search_images, "select_library_image", AsyncMock(return_value=item))
    monkeypatch.setattr(search_images, "get_image_library", lambda: library)
    sender = AsyncMock(return_value=sent)
    monkeypatch.setattr(search_images.send_service, "image_to_stream", sender)
    monkeypatch.setattr(search_images.send_service, "emoji_to_stream", sender)
    result = await search_images.handle_tool(
        ctx, SimpleNamespace(arguments={"query": "开心", "msg_id": target_id}, tool_name="search_images")
    )
    assert result["success"] == (target_id == "post:123" and sent)
    if target_id == "post:123":
        payload_key = "emoji_base64" if is_emoji else "image_base64"
        assert base64.b64decode(sender.call_args.kwargs[payload_key]) == png
        assert sender.call_args.kwargs["stream_id"] == "real-session"
        assert sender.call_args.kwargs["reply_message"] is target
        assert sender.call_args.kwargs["sync_to_maisaka_history"]
    else:
        sender.assert_not_called()
