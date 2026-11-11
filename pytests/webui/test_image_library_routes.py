from contextlib import contextmanager
from io import BytesIO
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import GifImagePlugin, Image
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

import importlib
import pytest

from src.common.database.database_model import Images, ImageType
from src.common.utils import image_path
from src.emoji_system.image_library import ImageLibrary
from src.webui.dependencies import require_auth
from src.webui.routers import emoji
from src.webui.routers.emoji import library as routes
from src.webui.routers.emoji import routes as emoji_routes
from src.webui.routers.emoji import support


@pytest.fixture
def setup(tmp_path, monkeypatch):
    library = ImageLibrary(tmp_path / "gallery", 16 * 1024 * 1024, 100)
    monkeypatch.setattr(routes, "get_image_library", lambda: library)
    monkeypatch.setattr(image_path, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(emoji_routes, "EMOJI_DIR", str(tmp_path / "emoji"))
    monkeypatch.setattr(routes, "generate_thumbnail", lambda path, file_hash: path)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Images.__table__.create(engine)

    @contextmanager
    def session():
        with Session(engine, expire_on_commit=False) as db:
            yield db
            db.commit()

    monkeypatch.setattr(routes, "get_db_session", session)
    manager_module = importlib.import_module("src.emoji_system.emoji_manager")
    monkeypatch.setattr(manager_module, "get_db_session", session)
    monkeypatch.setattr(routes.emoji_manager, "emojis", [])
    monkeypatch.setattr(routes.emoji_manager, "_emoji_num", 0)
    app = FastAPI()
    app.include_router(emoji.router, prefix="/api/webui")
    app.dependency_overrides[require_auth] = lambda: "test-session"
    with TestClient(app) as client:
        yield client, library, session
    engine.dispose()


def make_gif():
    stream = BytesIO()
    frames = [Image.new("RGB", (4, 4), color) for color in ("red", "green")]
    frames[0].save(stream, "GIF", save_all=True, append_images=frames[1:], duration=100, loop=0)
    return stream.getvalue()


def test_gallery_upload_browse_edit_retry_and_delete(setup):
    client, library, _ = setup
    data = make_gif()
    response = client.post(
        "/api/webui/emoji/library/upload", files={"file": ("开心.gif", data, "image/gif")}, data={"tags": "开心"}
    )
    assert response.status_code == 200
    item = response.json()["item"]
    image_id = item["id"]
    listing = client.get("/api/webui/emoji/library", params={"search": "开心"})
    assert listing.status_code == 200 and listing.json()["total"] == 1
    assert client.get(f"/api/webui/emoji/library/{image_id}/content?original=true").content == data
    assert client.patch(f"/api/webui/emoji/library/{image_id}", json={"tags": "手动,表情包"}).status_code == 200
    library.mark_caption(image_id, "failed")
    assert client.post("/api/webui/emoji/library/retry-tags").json() == {"queued": 1}
    assert library.get(image_id)["caption_status"] == "pending"
    assert client.delete(f"/api/webui/emoji/library/{image_id}").status_code == 200
    assert client.get("/api/webui/emoji/library").json()["total"] == 0
    assert client.get(f"/api/webui/emoji/library/{image_id}/content").status_code == 404


def test_gallery_adoption_immediately_joins_native_send_pool_and_keeps_original(setup, monkeypatch):
    client, library, session = setup
    monkeypatch.setattr(routes.global_config.emoji, "content_filtration", False)
    item, _ = library.add_bytes(make_gif(), "开心.gif", ["开心", "表情包"])
    response = client.post(f"/api/webui/emoji/library/{item['id']}/adopt")
    assert response.status_code == 200
    candidate = routes.emoji_manager.get_emoji_by_hash(item["id"])
    assert candidate is not None and candidate.full_path.read_bytes() == make_gif()
    with session() as db:
        record = db.exec(select(Images).where(Images.image_hash == item["id"])).one()
        assert record.image_type == ImageType.EMOJI and record.is_registered
        assert record.description == "开心,表情包"
    assert client.post(f"/api/webui/emoji/library/{item['id']}/adopt").status_code == 200
    assert len(routes.emoji_manager.emojis) == 1
    library.delete(item["id"])
    assert candidate.full_path.is_file()


def test_gallery_adoption_respects_ban_and_registration_limit(setup, monkeypatch):
    client, library, session = setup
    item, _ = library.add_bytes(make_gif(), "test.gif")
    monkeypatch.setattr(routes.global_config.emoji, "max_reg_num", 0)
    assert client.post(f"/api/webui/emoji/library/{item['id']}/adopt").status_code == 409
    with session() as db:
        db.add(
            Images(
                image_hash=item["id"],
                image_type=ImageType.EMOJI,
                description="",
                full_path="missing.gif",
                is_banned=True,
            )
        )
    assert client.post(f"/api/webui/emoji/library/{item['id']}/adopt").status_code == 400
    assert routes.emoji_manager.emojis == []


def test_gallery_scan_and_upload_validation(setup):
    client, library, _ = setup
    (library.images / "test.gif").write_bytes(make_gif())
    (library.images / "bad.png").write_bytes(b"bad")
    report = client.post("/api/webui/emoji/library/sync").json()
    assert report["added"] == 1 and len(report["errors"]) == 1
    assert (
        client.post("/api/webui/emoji/library/upload", files={"file": ("bad.png", b"bad", "image/png")}).status_code
        == 400
    )
    client.app.dependency_overrides.clear()
    assert client.get("/api/webui/emoji/library").status_code == 401


@pytest.mark.parametrize("original", [False, True])
def test_gallery_content_can_be_cached_privately(setup, original):
    client, library, _ = setup
    item, _ = library.add_bytes(make_gif(), "test.gif")
    response = client.get(f"/api/webui/emoji/library/{item['id']}/content", params={"original": original})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert response.content == make_gif()


@pytest.mark.parametrize("image_format", ["GIF", "PNG", "WEBP"])
def test_thumbnail_uses_first_frame_without_counting_gif_frames(tmp_path, monkeypatch, image_format):
    monkeypatch.setattr(support, "THUMBNAIL_CACHE_DIR", tmp_path / "thumbnails")
    frames = [Image.new("RGB", (240, 240), color) for color in ("red", "green")]
    source = tmp_path / f"animation.{image_format.lower()}"
    frames[0].save(source, image_format, save_all=True, append_images=frames[1:], duration=100, loop=0)

    def count_frames(_image):
        pytest.fail("生成首帧缩略图不应统计动图全部帧")

    monkeypatch.setattr(GifImagePlugin.GifImageFile, "n_frames", property(count_frames))
    thumbnail = support.generate_thumbnail(str(source), f"test-{image_format}")
    with Image.open(thumbnail) as preview:
        assert preview.size == (200, 200)
        red, green, blue = preview.convert("RGB").getpixel((100, 100))
        assert red > 240 and green < 15 and blue < 15


def test_rejected_adoption_keeps_only_gallery_file(setup, monkeypatch):
    client, library, _ = setup
    item, _ = library.add_bytes(make_gif(), "test.gif")
    monkeypatch.setattr(routes.emoji_manager, "review_emoji_for_registration", AsyncMock(return_value=False))
    assert client.post(f"/api/webui/emoji/library/{item['id']}/adopt").status_code == 400
    assert not (library.root.parent / "emoji").exists()
    assert library.read_bytes(item["id"]) == make_gif()
