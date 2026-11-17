from collections import Counter
from pathlib import Path

import os
import pytest

from src.webui.routers import system


def test_log_directory_statistics_preserve_fields_and_scan_each_file_once(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    files = {
        "app.log": (3, 1000),
        "maisaka_prompt/planner/chat-a/first.json": (5, 2000),
        "maisaka_prompt/planner/chat-a/second.json": (7, 4000),
        "maisaka_prompt/planner/chat-b/record.json": (11, 3000),
        "maisaka_prompt/replyer/chat-a/record.json": (13, 5000),
    }
    for relative_path, (size, modified_time) in files.items():
        path = log_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
        os.utime(path, (modified_time, modified_time))
    (log_dir / "empty").mkdir()
    monkeypatch.setattr(system, "_LOG_DIR", log_dir)
    file_paths = {log_dir / relative_path for relative_path in files}
    stat_calls = Counter()
    scan_calls = Counter()
    original_stat = Path.stat
    original_scandir = os.scandir

    def record_stat(path, *args, **kwargs):
        if path in file_paths:
            stat_calls[path] += 1
        return original_stat(path, *args, **kwargs)

    def record_scandir(path):
        scan_calls[Path(path)] += 1
        return original_scandir(path)

    with monkeypatch.context() as calls:
        calls.setattr(Path, "stat", record_stat)
        calls.setattr(os, "scandir", record_scandir)
        result = system._build_local_cache_log_directory_list_response()

    expected_stats = {
        "": (1, 3, 1000),
        "empty": (0, 0, 0),
        "maisaka_prompt": (4, 36, 5000),
        "maisaka_prompt/planner": (3, 23, 4000),
        "maisaka_prompt/planner/chat-a": (2, 12, 4000),
        "maisaka_prompt/planner/chat-b": (1, 11, 3000),
        "maisaka_prompt/replyer": (1, 13, 5000),
        "maisaka_prompt/replyer/chat-a": (1, 13, 5000),
    }
    expected = [
        {
            "relative_path": relative_path,
            "name": Path(relative_path).name if relative_path else "根目录文件",
            "full_path": str((log_dir / relative_path).resolve()),
            "depth": len(Path(relative_path).parts),
            "file_count": count,
            "total_size": size,
            "modified_time": modified_time,
            "root_files_only": not relative_path,
        }
        for relative_path, (count, size, modified_time) in expected_stats.items()
    ]
    assert result.model_dump() == {"success": True, "total": len(expected), "data": expected}
    assert stat_calls == Counter({path: 1 for path in file_paths})
    assert scan_calls == Counter({log_dir / relative_path: 1 for relative_path in expected_stats})


@pytest.mark.parametrize("kind", ["missing", "file", "empty"])
def test_log_directory_without_entries(tmp_path, monkeypatch, kind):
    log_dir = tmp_path / "logs"
    if kind == "file":
        log_dir.write_bytes(b"x")
    elif kind == "empty":
        log_dir.mkdir()
    monkeypatch.setattr(system, "_LOG_DIR", log_dir)

    assert system._build_log_directory_items() == []


@pytest.mark.parametrize("error", [FileNotFoundError, PermissionError])
def test_log_directory_skips_unreadable_files(tmp_path, monkeypatch, error):
    log_dir = tmp_path / "logs"
    nested_dir = log_dir / "planner" / "chat"
    nested_dir.mkdir(parents=True)
    unreadable = nested_dir / "record.json"
    unreadable.write_bytes(b"record")
    original_stat = Path.stat
    warnings = []

    def file_stat(path, *args, **kwargs):
        if path == unreadable:
            raise error("file unavailable")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(system, "_LOG_DIR", log_dir)
    monkeypatch.setattr(system.logger, "warning", warnings.append)
    with monkeypatch.context() as calls:
        calls.setattr(Path, "stat", file_stat)
        items = system._build_log_directory_items()

    assert [item.relative_path for item in items] == ["planner", "planner/chat"]
    assert all((item.file_count, item.total_size, item.modified_time) == (0, 0, 0) for item in items)
    assert len(warnings) == (0 if error is FileNotFoundError else 1)
