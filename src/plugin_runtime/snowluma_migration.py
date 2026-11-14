"""将已安装的 SnowLuma 适配器配置接续到内置版本。"""

from pathlib import Path
from typing import List, Sequence

import json
import shutil

from src.common.logger import get_logger

from .runner.manifest_validator import is_reserved_plugin_directory
from .runner.plugin_paths import get_plugin_config_path, is_builtin_plugin_path


logger = get_logger("plugin_runtime.snowluma_migration")
PLUGIN_ID = "maibot-team.snowluma-adapter"


def _copy_missing_file(source: Path, target: Path) -> None:
    if target.exists() or not source.is_file():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        shutil.copy2(source, temporary)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def migrate_snowluma_adapter(plugin_roots: Sequence[Path]) -> None:
    """保留实例配置与禁言状态，将外置源码备份到不参与发现的隐藏目录。"""
    builtin: List[Path] = []
    external: List[Path] = []
    roots = list(dict.fromkeys(Path(root).resolve() for root in plugin_roots))
    try:
        for root in roots:
            if not root.is_dir():
                continue
            for candidate in sorted(root.iterdir()):
                if not candidate.is_dir() or is_reserved_plugin_directory(candidate):
                    continue
                if not (candidate / "plugin.py").is_file():
                    continue
                try:
                    manifest = json.loads((candidate / "_manifest.json").read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if not isinstance(manifest, dict) or manifest.get("id") != PLUGIN_ID:
                    continue
                (builtin if is_builtin_plugin_path(candidate) else external).append(candidate)

        # 多个旧副本的配置归属不明确，交给现有重复 ID 隔离流程报告。
        if len(builtin) != 1 or len(external) != 1:
            return

        config_path = get_plugin_config_path(builtin[0], PLUGIN_ID)
        source = external[0]
        _copy_missing_file(source / "config.toml", config_path)
        _copy_missing_file(
            source.parent / "data" / "napcat_adapter" / "ban_state.json",
            config_path.parent / "ban_state.json",
        )

        backup_root = source.parent / ".builtin-backups"
        backup_root.mkdir(exist_ok=True)
        backup = backup_root / source.name
        suffix = 1
        while backup.exists():
            backup = backup_root / f"{source.name}.{suffix}"
            suffix += 1
        source.rename(backup)
        logger.info(f"SnowLuma 适配器已接续到内置版本，外置源码备份于 {backup}")
    except OSError as exc:
        # 复制和改名完成前始终保留旧源码，失败后重复 ID 检查会阻止双重连接。
        logger.error(f"SnowLuma 适配器迁移失败，旧文件已保留: {exc}")
