from pathlib import Path
from unittest.mock import AsyncMock, Mock

import asyncio
import pytest

from src.A_memorix import host_service as host_module
from src.A_memorix.core.runtime.runtime_writer_lock import RuntimeWriterLock
from src.A_memorix.core.storage.metadata_store import MetadataStore


@pytest.fixture
def host(tmp_path, monkeypatch):
    service = host_module.AMemorixHostService()
    service._config_cache = {"plugin": {"enabled": True}, "storage": {"data_dir": str(tmp_path / "memory")}}
    service._kernel = Mock(shutdown=AsyncMock(), _request_dedup_tasks={})
    service._runtime_state = "ready"
    monkeypatch.setattr(service, "start", AsyncMock())
    monkeypatch.setattr(host_module, "set_runtime_kernel", Mock())
    monkeypatch.setattr(host_module, "artifacts_root", lambda: tmp_path / "artifacts")
    return service


@pytest.mark.asyncio
async def test_clear_removes_all_memory_stores_and_reopens_empty(host, tmp_path):
    root = host.get_runtime_data_dir()
    store = MetadataStore(data_dir=root / "metadata")
    store.connect()
    store.add_paragraph("old memory", source="chat_summary:test")
    store.close()
    for name in ("graph", "vectors", "images/assets", "images/vectors", "imports",
                 "vector_quarantine", "vector_reconciliation_evidence"):
        folder = root / name
        folder.mkdir(parents=True)
        (folder / "old-memory").write_text("old", encoding="utf-8")
    for name in ("startup_write_queue.jsonl", "startup_write_queue.done.jsonl",
                 "startup_write_queue.failed.jsonl", "vector_recovery.json", "import_manifest.json"):
        (root / name).write_text("old", encoding="utf-8")
    artifacts = tmp_path / "artifacts" / "retrieval_tuning"
    artifacts.mkdir(parents=True)
    (artifacts / "report.json").write_text("old", encoding="utf-8")
    for name in ("MaiBot.db", "bot_config.toml", "unrelated.txt"):
        (root / name).write_text("keep", encoding="utf-8")
    (root / "images" / "original.jpg").write_bytes(b"original chat image")
    host._startup_queue_pending_count = 3
    host._startup_queue_cache_loaded = True
    old_kernel = host._kernel

    assert await host.clear_all_memory("清空全部记忆") == {"success": True}
    old_kernel.shutdown.assert_awaited_once()
    host.start.assert_awaited_once()
    assert host._kernel is None
    assert host._startup_queue_pending_count == 0
    assert not host._startup_queue_cache_loaded
    assert not artifacts.exists()
    assert {path.name for path in root.iterdir()} == {
        ".a_memorix_runtime_writer.lock", "images", "MaiBot.db", "bot_config.toml", "unrelated.txt",
    }
    assert list((root / "images").iterdir()) == [root / "images" / "original.jpg"]
    for name in ("MaiBot.db", "bot_config.toml", "unrelated.txt"):
        assert (root / name).read_text(encoding="utf-8") == "keep"
    fresh_store = MetadataStore(data_dir=root / "metadata")
    fresh_store.connect()
    try:
        assert fresh_store.query("SELECT COUNT(*) AS count FROM paragraphs")[0]["count"] == 0
    finally:
        fresh_store.close()
    assert await host.clear_all_memory("清空全部记忆") == {"success": True}


@pytest.mark.asyncio
@pytest.mark.parametrize("confirmation", ["", "确认", "清空全部记忆 "])
async def test_clear_requires_exact_confirmation(host, confirmation):
    with pytest.raises(ValueError, match="确认永久删除"):
        await host.clear_all_memory(confirmation)
    host._kernel.shutdown.assert_not_awaited()
    assert not host.get_runtime_data_dir().exists()


@pytest.mark.asyncio
async def test_clear_drains_inflight_call_and_rejects_new_calls(host, monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()

    async def write(*args):
        entered.set()
        await release.wait()
        return {"success": True}

    monkeypatch.setattr(host, "_invoke", write)
    ongoing = asyncio.create_task(host.invoke("ingest_text"))
    await entered.wait()
    clearing = asyncio.create_task(host.clear_all_memory("清空全部记忆"))
    await asyncio.sleep(0)
    assert not (await host.invoke("ingest_text"))["success"]
    host._kernel.shutdown.assert_not_awaited()
    with pytest.raises(RuntimeError, match="重复操作"):
        await host.clear_all_memory("清空全部记忆")
    release.set()
    assert (await ongoing)["success"]
    assert (await clearing)["success"]
    assert not host._active_calls


@pytest.mark.asyncio
async def test_failed_call_releases_clear_barrier_without_changing_error(host, monkeypatch):
    failure = TimeoutError("upstream timeout")
    monkeypatch.setattr(host, "_invoke", AsyncMock(side_effect=failure))
    with pytest.raises(TimeoutError) as caught:
        await host.invoke("search_memory")
    assert caught.value is failure
    assert not host._active_calls
    assert (await host.clear_all_memory("清空全部记忆"))["success"]


@pytest.mark.asyncio
async def test_disconnected_request_does_not_interrupt_clear(host):
    entered, release = asyncio.Event(), asyncio.Event()

    async def shutdown():
        entered.set()
        await release.wait()

    host._kernel.shutdown.side_effect = shutdown
    request = asyncio.create_task(host.clear_all_memory("清空全部记忆"))
    await entered.wait()
    request.cancel()
    with pytest.raises(asyncio.CancelledError):
        await request
    assert host._resetting
    assert not (await host.invoke("ingest_text"))["success"]
    release.set()
    assert (await host._clear_task)["success"]
    assert not host._resetting


@pytest.mark.asyncio
async def test_clear_waits_for_detached_search_before_closing_storage(host):
    entered, release = asyncio.Event(), asyncio.Event()

    async def detached_search():
        entered.set()
        await release.wait()

    search = asyncio.create_task(detached_search())
    host._kernel._request_dedup_tasks["search"] = search
    await entered.wait()
    clearing = asyncio.create_task(host.clear_all_memory("清空全部记忆"))
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    host._kernel.shutdown.assert_not_awaited()
    release.set()
    assert (await clearing)["success"]
    assert search.done()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["shutdown", "filesystem"])
async def test_failed_clear_blocks_runtime_until_retry(host, monkeypatch, failure):
    delete_files = Mock()
    monkeypatch.setattr(host, "_clear_memory_files", delete_files)
    if failure == "shutdown":
        host._kernel.shutdown.side_effect = RuntimeError("shutdown failed")
    else:
        delete_files.side_effect = OSError("filesystem failed")
    result = await host.clear_all_memory("清空全部记忆")
    assert not result["success"]
    assert "重试" in result["error"]
    host.start.assert_not_awaited()
    if failure == "shutdown":
        delete_files.assert_not_called()
        host._kernel.shutdown.side_effect = None
    assert not (await host.invoke("ingest_text"))["success"]
    await host._ensure_startup_task()
    assert host._startup_task is None
    with pytest.raises(RuntimeError, match="清空"):
        await host.reload()
    delete_files.side_effect = None
    assert (await host.clear_all_memory("清空全部记忆"))["success"]
    assert not host._reset_failed


def test_clear_refuses_other_runtime_writer(host):
    root = host.get_runtime_data_dir()
    lock = RuntimeWriterLock(root / ".a_memorix_runtime_writer.lock")
    lock.acquire()
    data = root / "startup_write_queue.jsonl"
    data.write_text("keep", encoding="utf-8")
    try:
        with pytest.raises(RuntimeError, match="活动写者"):
            host._clear_memory_files()
        assert data.read_text(encoding="utf-8") == "keep"
    finally:
        lock.release()


def test_clear_validates_all_paths_before_deleting(host, tmp_path, monkeypatch):
    root = host.get_runtime_data_dir()
    metadata = root / "metadata"
    metadata.mkdir(parents=True)
    data = metadata / "keep.txt"
    data.write_text("keep", encoding="utf-8")
    original_resolve = Path.resolve

    def resolve(path, *args, **kwargs):
        if path == root / "images" / "assets":
            return tmp_path / "outside"
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    with pytest.raises(ValueError, match="越界"):
        host._clear_memory_files()
    assert data.read_text(encoding="utf-8") == "keep"


@pytest.mark.asyncio
async def test_interrupted_clear_stays_blocked_after_restart_until_retry(host, monkeypatch):
    root = host.get_runtime_data_dir()
    (root / "metadata").mkdir(parents=True)
    with monkeypatch.context() as patch:
        patch.setattr(host_module.shutil, "rmtree", Mock(side_effect=OSError("disk error")))
        with pytest.raises(OSError, match="disk error"):
            host._clear_memory_files()
    assert (root / ".memory_clear_pending").exists()
    restarted = host_module.AMemorixHostService()
    restarted._config_cache = host._config_cache
    await restarted.start()
    assert restarted._startup_task is None
    assert restarted._reset_failed
    assert not (await restarted.invoke("ingest_text"))["success"]
    monkeypatch.setattr(restarted, "start", AsyncMock())
    assert (await restarted.clear_all_memory("清空全部记忆"))["success"]
    assert not (root / ".memory_clear_pending").exists()
    restarted.start.assert_awaited_once()
