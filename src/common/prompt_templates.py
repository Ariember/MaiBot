from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from string import Formatter
from typing import Any, Dict
from tomlkit import parse as parse_toml

import json
import logging
import re

from .paths import get_instance_root, resource_path

logger = logging.getLogger("maibot.prompt_templates")

PROJECT_ROOT = get_instance_root()
PROMPTS_ROOT = resource_path("prompts").resolve()
CUSTOM_PROMPTS_ROOT = (PROJECT_ROOT / "data" / "custom_prompts").resolve()
PROMPT_EXTENSIONS = (".prompt",)
SAFE_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
_PROMPT_CACHE_REVISION = 0


def extract_prompt_placeholders(template: str) -> set[str]:
    return {
        field_name.split(".", maxsplit=1)[0].split("[", maxsplit=1)[0]
        for _, field_name, _, _ in Formatter().parse(template)
        if field_name
    }


@dataclass(frozen=True)
class PromptMetadata:
    display_name: str = ""
    advanced: bool = False
    description: str = ""


@dataclass(frozen=True)
class PromptTemplateInfo:
    path: Path
    metadata: PromptMetadata


@dataclass(frozen=True)
class ResolvedPromptTemplate:
    path: Path
    template: str
    customized: bool


def get_prompts_root(prompts_root: Path | None = None) -> Path:
    return (prompts_root or PROMPTS_ROOT).resolve()


def get_custom_prompts_root(
    custom_prompts_root: Path | None = None,
    prompts_root: Path | None = None,
) -> Path:
    if custom_prompts_root is not None:
        return custom_prompts_root.resolve()
    if prompts_root is not None:
        return (prompts_root.resolve().parent / "data" / "custom_prompts").resolve()
    return CUSTOM_PROMPTS_ROOT


def normalize_prompt_name(name: str) -> str:
    candidate_name = name.strip()
    for suffix in PROMPT_EXTENSIONS:
        if candidate_name.endswith(suffix):
            candidate_name = candidate_name[: -len(suffix)]
            break

    if candidate_name in {".", ".."} or not candidate_name or not SAFE_SEGMENT_PATTERN.fullmatch(candidate_name):
        raise ValueError(f"Prompt 名称 '{name}' 非法")
    return candidate_name


def normalize_prompt_category(category: str | None) -> str | None:
    if category is None:
        return None

    category_parts = [part for part in category.strip().split("/") if part]
    if not category_parts:
        raise ValueError(f"Prompt 分类 '{category}' 非法")

    for part in category_parts:
        if part in {".", ".."} or not SAFE_SEGMENT_PATTERN.fullmatch(part):
            raise ValueError(f"Prompt 分类 '{category}' 非法")
    return "/".join(category_parts)


def iter_prompt_files(directory: Path, recursive: bool = True) -> list[Path]:
    if not directory.exists():
        return []

    search = directory.rglob if recursive else directory.glob
    prompt_files: list[Path] = []
    for suffix in PROMPT_EXTENSIONS:
        prompt_files.extend(path for path in search(f"*{suffix}") if path.is_file())
    return sorted(set(prompt_files))


def _raise_duplicate_prompt_name(name: str, first_path: Path, second_path: Path, prompts_root: Path) -> None:
    path_a = first_path.relative_to(prompts_root).as_posix()
    path_b = second_path.relative_to(prompts_root).as_posix()
    raise ValueError(f"Prompt 模板名称 '{name}' 重复：{path_a} 与 {path_b}")


def _coerce_metadata(raw_metadata: Any) -> PromptMetadata:
    if not isinstance(raw_metadata, dict):
        return PromptMetadata()

    display_name = raw_metadata.get("display_name", "")
    advanced = raw_metadata.get("advanced", False)
    description = raw_metadata.get("description", "")

    return PromptMetadata(
        display_name=display_name if isinstance(display_name, str) else "",
        advanced=advanced if isinstance(advanced, bool) else False,
        description=description if isinstance(description, str) else "",
    )


def _read_metadata_file(metadata_path: Path) -> dict[str, Any]:
    if not metadata_path.is_file():
        return {}

    try:
        if metadata_path.suffix == ".json":
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        else:
            metadata = parse_toml(metadata_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"读取 Prompt 元信息文件 {metadata_path} 失败：{exc}")
        return {}

    return dict(metadata) if isinstance(metadata, dict) else {}


def _extract_template_metadata(metadata: dict[str, Any], prompt_name: str) -> dict[str, Any]:
    templates = metadata.get("templates")
    if isinstance(templates, dict) and isinstance(templates.get(prompt_name), dict):
        return dict(templates[prompt_name])

    prompt_metadata = metadata.get(prompt_name)
    if isinstance(prompt_metadata, dict):
        return dict(prompt_metadata)

    return metadata if any(key in metadata for key in ("display_name", "advanced", "description")) else {}


def _load_prompt_metadata(prompt_path: Path, metadata_cache: Dict[Path, Dict[str, Any]]) -> PromptMetadata:
    prompt_name = prompt_path.stem
    metadata_sources = (
        prompt_path.with_name(f"{prompt_name}.meta.toml"),
        prompt_path.with_name(f"{prompt_name}.meta.json"),
        prompt_path.parent / ".meta.toml",
        prompt_path.parent / ".meta.json",
    )

    merged_metadata: dict[str, Any] = {}
    for metadata_path in reversed(metadata_sources):
        if metadata_path not in metadata_cache:
            metadata_cache[metadata_path] = _read_metadata_file(metadata_path)
        raw_metadata = metadata_cache[metadata_path]
        merged_metadata.update(_extract_template_metadata(raw_metadata, prompt_name))

    return _coerce_metadata(merged_metadata)


def _scan_prompt_directory(directory: Path, prompts_root: Path) -> dict[str, PromptTemplateInfo]:
    prompt_paths: dict[str, PromptTemplateInfo] = {}
    # 同一轮扫描共享解析结果；下次扫描重新读取，确保元信息修改立即生效。
    metadata_cache: Dict[Path, Dict[str, Any]] = {}
    for prompt_path in iter_prompt_files(directory):
        prompt_name = prompt_path.stem
        existing_info = prompt_paths.get(prompt_name)
        if existing_info is not None:
            _raise_duplicate_prompt_name(prompt_name, existing_info.path, prompt_path, prompts_root)
        prompt_paths[prompt_name] = PromptTemplateInfo(
            path=prompt_path, metadata=_load_prompt_metadata(prompt_path, metadata_cache)
        )
    return prompt_paths


def _iter_prompt_path_candidates(base_dir: Path, name: str, category: str | None = None) -> list[Path]:
    candidates: list[Path] = []
    for suffix in PROMPT_EXTENSIONS:
        if category is not None:
            candidates.append((base_dir / category / f"{name}{suffix}").resolve())
        candidates.append((base_dir / f"{name}{suffix}").resolve())
    return candidates


def _resolve_custom_prompt_path(
    name: str,
    category: str | None,
    custom_prompts_root: Path,
) -> Path | None:
    custom_dir = custom_prompts_root / "zh-CN"
    for candidate_path in _iter_prompt_path_candidates(custom_dir, name, category):
        if candidate_path.is_file():
            return candidate_path
    return None


def _resolve_legacy_custom_prompt_path(name: str, custom_prompts_root: Path) -> Path | None:
    for suffix in PROMPT_EXTENSIONS:
        candidate_path = (custom_prompts_root / f"{name}{suffix}").resolve()
        if candidate_path.is_file():
            return candidate_path
    return None


def list_prompt_templates(prompts_root: Path | None = None) -> dict[str, PromptTemplateInfo]:
    resolved_prompts_root = get_prompts_root(prompts_root)
    return _scan_prompt_directory(resolved_prompts_root / "zh-CN", resolved_prompts_root)


def resolve_prompt_path(
    name: str,
    category: str | None = None,
    prompts_root: Path | None = None,
    custom_prompts_root: Path | None = None,
    include_legacy_custom: bool = False,
    include_custom: bool = True,
) -> Path:
    resolved_prompts_root = get_prompts_root(prompts_root)
    resolved_custom_prompts_root = get_custom_prompts_root(custom_prompts_root, prompts_root)
    normalized_name = normalize_prompt_name(name)
    normalized_category = normalize_prompt_category(category)

    if include_custom:
        custom_path = _resolve_custom_prompt_path(
            normalized_name, normalized_category, resolved_custom_prompts_root
        )
        if custom_path is not None:
            return custom_path
        if include_legacy_custom:
            legacy_custom_path = _resolve_legacy_custom_prompt_path(normalized_name, resolved_custom_prompts_root)
            if legacy_custom_path is not None:
                return legacy_custom_path

    # 允许带 category 的调用继续复用根目录下的平铺模板。
    for candidate_path in _iter_prompt_path_candidates(
        resolved_prompts_root / "zh-CN", normalized_name, normalized_category
    ):
        if candidate_path.is_file():
            return candidate_path
    raise FileNotFoundError(f"未找到 Prompt 模板 '{normalized_name}'")


@lru_cache(maxsize=None)
def _read_prompt_template(prompt_path: Path) -> str:
    return prompt_path.read_text(encoding="utf-8")


def load_prompt_template(
    name: str,
    category: str | None = None,
    prompts_root: Path | None = None,
    custom_prompts_root: Path | None = None,
    include_legacy_custom: bool = False,
    include_custom: bool = True,
) -> ResolvedPromptTemplate:
    resolved_prompts_root = get_prompts_root(prompts_root)
    resolved_custom_prompts_root = get_custom_prompts_root(custom_prompts_root, prompts_root)
    normalized_name = normalize_prompt_name(name)
    prompt_path = resolve_prompt_path(
        name=normalized_name,
        category=category,
        prompts_root=resolved_prompts_root,
        custom_prompts_root=resolved_custom_prompts_root,
        include_legacy_custom=include_legacy_custom,
        include_custom=include_custom,
    )
    return ResolvedPromptTemplate(
        path=prompt_path,
        template=_read_prompt_template(prompt_path),
        customized=prompt_path.is_relative_to(resolved_custom_prompts_root),
    )


def _format_prompt_template(name: str, template: str, **kwargs: object) -> str:
    if not kwargs:
        return template

    try:
        return template.format(**kwargs)
    except KeyError as exc:
        missing_placeholder = exc.args[0]
        raise KeyError(f"Prompt 模板 '{name}' 缺少占位符 '{missing_placeholder}'") from exc
    except Exception as exc:
        logger.error(f"渲染 Prompt 模板 '{name}' 失败: {exc}")
        raise


def load_prompt(
    name: str,
    category: str | None = None,
    prompts_root: Path | None = None,
    custom_prompts_root: Path | None = None,
    **kwargs: object,
) -> str:
    normalized_name = normalize_prompt_name(name)
    resolved_template = load_prompt_template(
        name=normalized_name,
        category=category,
        prompts_root=prompts_root,
        custom_prompts_root=custom_prompts_root,
    )
    if resolved_template.customized and kwargs:
        try:
            return resolved_template.template.format(**kwargs)
        except (KeyError, IndexError, ValueError, AttributeError):
            # 旧自定义模板可能仍引用已移除的参数；保留原文件，改用当前内置模板。
            default_template = load_prompt_template(
                name=normalized_name,
                category=category,
                prompts_root=prompts_root,
                custom_prompts_root=custom_prompts_root,
                include_custom=False,
            )
            rendered = _format_prompt_template(normalized_name, default_template.template, **kwargs)
            logger.warning(f"Prompt 模板 '{normalized_name}' 已过期，使用默认模板")
            return rendered
    return _format_prompt_template(normalized_name, resolved_template.template, **kwargs)


def clear_prompt_cache() -> None:
    global _PROMPT_CACHE_REVISION
    _PROMPT_CACHE_REVISION += 1
    _read_prompt_template.cache_clear()


def get_prompt_cache_revision() -> int:
    return _PROMPT_CACHE_REVISION
