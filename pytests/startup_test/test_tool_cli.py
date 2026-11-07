"""在独立目录验证 CLI 不依赖仓库工作目录，初始化不会覆盖用户配置。"""

from pathlib import Path
from typing import List

import os
import subprocess
import sys

import pytest

from src.common.instance_lock import register_instance

ROOT = Path(__file__).resolve().parents[2]


def invoke(directory: Path, args: List[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.pop("MAIBOT_INSTANCE_DIR", None)
    env.pop("MAIBOT_INITIALIZE_ONLY", None)
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "src.cli.tool", *args],
        cwd=directory, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )


def test_help_and_version_do_not_initialize(tmp_path: Path) -> None:
    for args in (["--help"], ["--version"]):
        result = invoke(tmp_path, args)
        assert result.returncode == 0, result.stderr
    assert not list(tmp_path.iterdir())


def test_init_preserves_existing_files_and_does_not_create_database(tmp_path: Path) -> None:
    instance = tmp_path / "麦麦 instance"
    result = invoke(tmp_path, ["init", "-d", str(instance)])
    assert result.returncode == 0, result.stderr
    bot_config = instance / "config" / "bot_config.toml"
    model_config = instance / "config" / "model_config.toml"
    bot_config.write_bytes(bot_config.read_bytes() + b'\n# user setting\n')
    before = (bot_config.read_bytes(), model_config.read_bytes())
    result = invoke(tmp_path, ["init", "-d", str(instance)])
    assert result.returncode == 0, result.stderr
    assert before == (bot_config.read_bytes(), model_config.read_bytes())
    assert not (instance / "data" / "MaiBot.db").exists()
    assert not (instance / "eula.confirmed").exists()
    for name in ("data", "logs", "plugins", "temp"):
        assert (instance / name).is_dir()


def test_run_requires_initialized_instance(tmp_path: Path) -> None:
    result = invoke(tmp_path, ["run"])
    assert result.returncode == 2
    assert "maibot init" in result.stderr
    assert not list(tmp_path.iterdir())


def invoke_runner(directory: Path, entry: str, *, supervised: bool = False) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["MAIBOT_INSTANCE_DIR"] = str(directory)
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("MAIBOT_WORKER_PROCESS", None)
    env.pop("MAIBOT_RUNNER_SUPERVISED", None)
    if supervised:
        env["MAIBOT_RUNNER_SUPERVISED"] = "1"
    # 只执行真实启动入口及文件锁；禁止创建 Worker、访问业务数据或执行更新。
    script = f"""
from unittest.mock import patch
import runpy
import sys

def run_runner(*args):
    print("runner-started")
    return 0

with (
    patch("src.common.process_runner.run_runner", run_runner),
    patch("src.common.self_update.clear_pending_update"),
    patch("src.config.legacy_upgrade_confirmation.require_legacy_upgrade_confirmation"),
):
    if {entry!r} == "bot":
        runpy.run_path({str(ROOT / 'bot.py')!r}, run_name="__main__")
    elif {entry!r} == "cli":
        sys.argv = ["maibot", "run", "--directory", {str(directory)!r}]
        runpy.run_module("src.cli.tool", run_name="__main__")
    else:
        runpy.run_module("src.runtime", run_name="__main__")
"""
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=directory, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )


@pytest.mark.parametrize("entry", ["bot", "cli", "runtime"])
def test_run_refuses_duplicate_before_starting_worker(tmp_path: Path, entry: str) -> None:
    config = tmp_path / "config"
    config.mkdir()
    for name in ("bot_config.toml", "model_config.toml"):
        (config / name).touch()
    with register_instance(tmp_path):
        result = invoke_runner(tmp_path, entry)
    assert result.returncode != 0
    assert "这个实例正在运行" in result.stderr
    assert "runner-started" not in result.stdout

    result = invoke_runner(tmp_path, entry)
    assert result.returncode == 0, result.stderr
    assert "runner-started" in result.stdout


def test_supervised_runner_reuses_outer_instance_lease(tmp_path: Path) -> None:
    with register_instance(tmp_path):
        result = invoke_runner(tmp_path, "runtime", supervised=True)
        assert result.returncode == 0, result.stderr
        assert "runner-started" in result.stdout
        with pytest.raises(RuntimeError, match="这个实例正在运行"):
            register_instance(tmp_path)
