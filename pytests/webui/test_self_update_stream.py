from threading import Event
import asyncio
import json

import pytest

from src.common.self_update import LocalState, SelfUpdateError, UpdateCheck
from src.common.self_update import PendingUpdate
from src.webui.routers import self_update as module


@pytest.mark.asyncio
async def test_image_apply_queues_without_restarting_worker(monkeypatch):
    pending = PendingUpdate("sha256:" + "2" * 64, "sha256:" + "1" * 64, "latest", 123.0, "ghcr")
    monkeypatch.setattr(module, "request_update", lambda *args, **kwargs: pending)

    def restart():
        pytest.fail("镜像更新不能先重启旧 Worker")

    monkeypatch.setattr(module, "schedule_restart", restart)
    response = await module.apply_self_update(module.SelfUpdateApplyRequest(source_id="ghcr", expected_commit=pending.target_commit))
    assert response.success and response.requested_at == 123.0


@pytest.mark.parametrize("source", ["pypi", "tuna", "aliyun", "cnb"])
def test_removed_sources_are_rejected(source):
    with pytest.raises(ValueError):
        module.SelfUpdateCheckRequest(source_id=source)


@pytest.mark.asyncio
async def test_stream_delivers_progress_before_check_finishes(monkeypatch):
    release = Event()
    local = LocalState(version="1.0.0", branch="dev", commit="1" * 40)

    def check(**kwargs):
        kwargs["on_progress"]("cnb：读取 dev 分支信息")
        assert release.wait(2)
        return UpdateCheck(local=local)

    monkeypatch.setattr(module.self_update_cache, "get", check)
    monkeypatch.setattr(module, "read_last_result", lambda: None)
    stream = module._stream_check_events(module.SelfUpdateCheckRequest(source_id="github"))
    try:
        first = json.loads(await asyncio.wait_for(anext(stream), timeout=1))
        assert first == {"type": "progress", "message": "cnb：读取 dev 分支信息"}
        assert not release.is_set()
        release.set()
        remaining = [json.loads(line) async for line in stream]
        assert [event["type"] for event in remaining] == ["result"]
        assert remaining[0]["status"]["current_commit"] == local.commit
    finally:
        release.set()
        await stream.aclose()


@pytest.mark.asyncio
async def test_stream_retains_error_details(monkeypatch):
    message = "cnb 检查失败（比较本地与远端提交）：TimeoutError: timed out"

    def check(**kwargs):
        kwargs["on_progress"]("cnb：比较本地与远端提交")
        raise SelfUpdateError("fetch_failed", message)

    monkeypatch.setattr(module.self_update_cache, "get", check)
    events = [json.loads(line) async for line in module._stream_check_events(
        module.SelfUpdateCheckRequest(source_id="github"),
    )]
    assert [event["type"] for event in events] == ["progress", "error"]
    assert events[-1]["message"] == message


@pytest.mark.asyncio
async def test_disconnect_drops_late_worker_events(monkeypatch):
    release = Event()
    finished = Event()

    def check(**kwargs):
        kwargs["on_progress"]("等待更新检查队列")
        assert release.wait(2)
        kwargs["on_progress"]("cnb：读取 dev 分支信息")
        finished.set()
        raise SelfUpdateError("fetch_failed", "timed out")

    monkeypatch.setattr(module.self_update_cache, "get", check)
    stream = module._stream_check_events(module.SelfUpdateCheckRequest(source_id="github"))
    try:
        await asyncio.wait_for(anext(stream), timeout=1)
        await stream.aclose()
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 1)
