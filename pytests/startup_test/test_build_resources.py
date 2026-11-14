"""安装包必须携带本仓库构建的 WebUI。"""

from pathlib import Path
from unittest.mock import Mock

import runpy
import sys

import pytest


@pytest.fixture
def build_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    base_build_py = type("build_py", (), {"run": lambda self: None})
    monkeypatch.setitem(sys.modules, "setuptools", Mock())
    monkeypatch.setitem(sys.modules, "setuptools.command.build_py", Mock(build_py=base_build_py))
    namespace = runpy.run_path(str(Path(__file__).resolve().parents[2] / "setup.py"))
    command = namespace["BuildPy"]()
    monkeypatch.setitem(command.run.__func__.__globals__, "__file__", str(tmp_path / "setup.py"))
    command.build_lib = str(tmp_path / "build")
    return command


def test_build_requires_dashboard_dist(build_command) -> None:
    with pytest.raises(RuntimeError, match="dashboard/dist/index.html.*bun run build"):
        build_command.run()


def test_build_collects_dashboard_assets_and_version(build_command, tmp_path: Path) -> None:
    dashboard = tmp_path / "dashboard"
    assets = dashboard / "dist" / "assets" / "chunks"
    assets.mkdir(parents=True)
    index = b'<html><script src="/assets/chunks/app.js"></script></html>\n'
    script = b"console.log('dashboard');\n"
    package = b'{"name":"maibot-dashboard","version":"1.9.15"}\n'
    (dashboard / "dist" / "index.html").write_bytes(index)
    (assets / "app.js").write_bytes(script)
    (dashboard / "package.json").write_bytes(package)
    for name in ("pyproject.toml", "EULA.md", "PRIVACY.md"):
        (tmp_path / name).write_text("resource", encoding="utf-8")
    (tmp_path / "changelogs").mkdir()
    (tmp_path / "changelogs" / "changelog.md").write_text("changes", encoding="utf-8")

    build_command.run()

    bundled = Path(build_command.build_lib) / "src" / "_resources" / "dashboard"
    assert (bundled / "dist" / "index.html").read_bytes() == index
    assert (bundled / "dist" / "assets" / "chunks" / "app.js").read_bytes() == script
    assert (bundled / "package.json").read_bytes() == package
