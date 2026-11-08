from io import BytesIO

from PIL import Image

import pytest

from src.emoji_system.image_library import ImageLibrary


@pytest.fixture
def png():
    stream = BytesIO()
    Image.new("RGB", (4, 4), "red").save(stream, format="PNG")
    return stream.getvalue()


@pytest.fixture
def library(tmp_path):
    return ImageLibrary(tmp_path / "data", 1024 * 1024, 10)


def test_import_deduplicates_merges_tags_and_survives_restart(library, png):
    item, added = library.add_bytes(png, "开心.png", ["开心"])
    assert added
    _, added = library.add_bytes(png, "复制.png", ["表情包"])
    assert not added
    reopened = ImageLibrary(library.root, 1024 * 1024, 10)
    assert reopened.get(item["id"])["tags"] == ["开心", "表情包"]
    assert reopened.read_bytes(item["id"]) == png
    assert reopened.candidates("发一张开心的表情包")[0]["score"] > 0


def test_rejects_non_images_size_and_capacity(library, png):
    with pytest.raises(ValueError, match="无法读取"):
        library.add_bytes(b"not a picture", "fake.png")
    library.max_bytes = 1
    with pytest.raises(ValueError, match="大小"):
        library.add_bytes(png, "large.png")
    library.max_bytes = 1024
    library.max_images = 0
    with pytest.raises(ValueError, match="容量"):
        library.add_bytes(png, "full.png")


def test_default_directory_scan_indexes_in_place_and_reports_bad_files(library, png):
    directory = library.images / "表情包"
    directory.mkdir()
    (directory / "开心.png").write_bytes(png)
    (directory / "bad.jpg").write_bytes(b"bad")
    result = library.sync()
    assert result["added"] == 1 and len(result["errors"]) == 1
    item = library.list_items()[0]
    assert item["tags"] == ["开心", "表情包"]
    assert item["rel_path"] == "images/表情包/开心.png"
    assert list(library.images.rglob("*.png")) == [directory / "开心.png"]
    assert library.read_bytes(item["id"]) == png


def test_rescan_preserves_edited_tags_and_completed_captions(library, png):
    (library.images / "开心.png").write_bytes(png)
    library.sync()
    item = library.list_items()[0]
    library.set_tags(item["id"], ["手动"])
    library.set_tags(item["id"], ["表情包"], automatic=True)
    assert library.sync()["existing"] == 1
    assert library.get(item["id"])["tags"] == ["手动", "表情包"]
    assert library.get(item["id"])["caption_status"] == "done"


def test_deleted_files_free_capacity_before_scanning_new_files(library, png):
    library.max_images = 1
    item, _ = library.add_bytes(png, "a.png")
    (library.root / item["rel_path"]).unlink()
    stream = BytesIO()
    Image.new("RGB", (4, 4), "green").save(stream, format="PNG")
    (library.images / "新图.png").write_bytes(stream.getvalue())
    result = library.sync()
    assert result["removed"] == 1 and result["added"] == 1
    assert result["errors"] == []
    assert library.list_items()[0]["rel_path"] == "images/新图.png"


def test_renamed_files_keep_identity_and_completed_captions(library, png):
    item, _ = library.add_bytes(png, "a.png", ["手动"])
    library.set_tags(item["id"], ["表情包"], automatic=True)
    (library.root / item["rel_path"]).rename(library.images / "开心.png")
    result = library.sync()
    assert result["existing"] == 1 and result["removed"] == 0
    current = library.get(item["id"])
    assert current["rel_path"] == "images/开心.png"
    assert current["caption_status"] == "done"
    assert {"手动", "表情包"} <= set(current["tags"])


def test_replacing_a_file_refreshes_identity_and_auto_tags(library, png):
    path = library.images / "开心.png"
    path.write_bytes(png)
    library.sync()
    previous = library.list_items()[0]
    library.set_tags(previous["id"], ["红色"], automatic=True)
    stream = BytesIO()
    Image.new("RGB", (4, 4), "green").save(stream, format="PNG")
    path.write_bytes(stream.getvalue())
    assert library.sync()["added"] == 1
    items = library.list_items()
    assert len(items) == 1 and items[0]["id"] != previous["id"]
    assert items[0]["auto_tags"] == [] and items[0]["caption_status"] == "pending"
    assert library.read_bytes(items[0]["id"]) == stream.getvalue()


def test_corrupted_files_are_removed_from_index_but_kept_on_disk(library, png):
    path = library.images / "a.png"
    path.write_bytes(png)
    library.sync()
    path.write_bytes(b"broken")
    result = library.sync()
    assert result["removed"] == 1 and len(result["errors"]) == 1
    assert library.list_items() == []
    assert path.read_bytes() == b"broken"


def test_scanning_existing_managed_storage_does_not_add_hashes_as_tags(library, png):
    item, _ = library.add_bytes(png, "a.png", ["手动"])
    library.set_tags(item["id"], ["表情包"], automatic=True)
    assert library.sync()["existing"] == 1
    assert library.get(item["id"])["tags"] == ["手动", "表情包"]
    assert library.get(item["id"])["caption_status"] == "done"


def test_manual_tags_survive_auto_tag_update_and_delete(library, png):
    item, _ = library.add_bytes(png, "a.png", ["手动"])
    library.set_tags(item["id"], ["开心"], automatic=True)
    assert library.get(item["id"])["tags"] == ["手动", "开心"]
    assert library.candidates("开心", only_memes=True) == []
    library.delete(item["id"])
    assert library.list_items() == []
    with pytest.raises(ValueError, match="不存在"):
        library.read_bytes(item["id"])
