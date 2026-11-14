"""构建时收集运行所需的只读资源，不复制任何用户配置或数据。"""

from pathlib import Path
from setuptools import setup
from setuptools.command.build_py import build_py

import shutil


class BuildPy(build_py):
    def run(self) -> None:
        root = Path(__file__).resolve().parent
        dashboard = root / "dashboard"
        if not (dashboard / "dist" / "index.html").is_file():
            raise RuntimeError("缺少 dashboard/dist/index.html，请先在 dashboard 目录执行 bun install --frozen-lockfile 和 bun run build")
        super().run()
        destination = Path(self.build_lib) / "src" / "_resources"
        destination.mkdir(parents=True, exist_ok=True)
        for name in ("prompts", "locales"):
            for source in (root / name).rglob("*"):
                if source.is_file() and source.suffix in {".prompt", ".toml", ".json"}:
                    target = destination / name / source.relative_to(root / name)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
        for name in ("pyproject.toml", "EULA.md", "PRIVACY.md"):
            shutil.copy2(root / name, destination / name)
        shutil.copytree(dashboard / "dist", destination / "dashboard" / "dist", dirs_exist_ok=True)
        shutil.copy2(dashboard / "package.json", destination / "dashboard" / "package.json")
        (destination / "changelogs").mkdir(exist_ok=True)
        shutil.copy2(root / "changelogs" / "changelog.md", destination / "changelogs" / "changelog.md")


setup(cmdclass={"build_py": BuildPy}, options={"build": {"build_base": "build/maibot"}})
