from __future__ import annotations

from pathlib import Path

import pytest

from src.common import prompt_templates
from src.common.prompt_templates import (
    PROMPTS_ROOT,
    clear_prompt_cache,
    extract_prompt_placeholders,
    list_prompt_templates,
    load_prompt,
)
from src.prompt.prompt_manager import PromptManager


@pytest.fixture(autouse=True)
def clear_template_cache() -> None:
    clear_prompt_cache()
    yield
    clear_prompt_cache()


def write_prompt(prompt_dir: Path, name: str, content: str) -> None:
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / f"{name}.prompt").write_text(content, encoding="utf-8")


def test_load_prompt_does_not_fall_back_to_legacy_root(tmp_path: Path) -> None:
    prompts_root = tmp_path / "prompts"
    write_prompt(prompts_root, "replyer", "Legacy {user_name}")

    with pytest.raises(FileNotFoundError):
        load_prompt("replyer", prompts_root=prompts_root, user_name="Mai")


def test_load_prompt_with_category_uses_chinese_root(tmp_path: Path) -> None:
    prompts_root = tmp_path / "prompts"
    write_prompt(prompts_root / "zh-CN", "replyer", "你好，{user_name}")

    rendered = load_prompt("replyer", category="chat", prompts_root=prompts_root, user_name="Mai")

    assert rendered == "你好，Mai"


def test_load_prompt_prefers_custom_prompt_override(tmp_path: Path) -> None:
    prompts_root = tmp_path / "prompts"
    custom_prompts_root = tmp_path / "data" / "custom_prompts"
    write_prompt(prompts_root / "zh-CN", "replyer", "Base {user_name}")
    write_prompt(custom_prompts_root / "zh-CN", "replyer", "Custom {user_name}")

    rendered = load_prompt(
        "replyer",
        prompts_root=prompts_root,
        custom_prompts_root=custom_prompts_root,
        user_name="Mai",
    )

    assert rendered == "Custom Mai"


def test_load_prompt_raises_on_missing_placeholder(tmp_path: Path) -> None:
    prompts_root = tmp_path / "prompts"
    write_prompt(prompts_root / "zh-CN", "replyer", "你好，{user_name}，现在是 {current_time}")

    with pytest.raises(KeyError) as exc_info:
        load_prompt("replyer", prompts_root=prompts_root, user_name="Mai")

    assert "current_time" in str(exc_info.value)


@pytest.mark.parametrize("outdated_template", ["Old {removed_name}", "Old {user_name", "Old {}"])
def test_outdated_custom_prompt_uses_builtin_template(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, outdated_template: str
) -> None:
    prompts_root = tmp_path / "prompts"
    custom_root = tmp_path / "custom"
    write_prompt(prompts_root / "zh-CN", "replyer", "默认 {user_name}")
    write_prompt(custom_root / "zh-CN", "replyer", outdated_template)

    assert load_prompt(
        "replyer", prompts_root=prompts_root,
        custom_prompts_root=custom_root, user_name="Mai",
    ) == "默认 Mai"
    assert "已过期，使用默认模板" in caplog.text
    assert all(record.exc_info is None and record.levelname == "WARNING" for record in caplog.records)
    assert (custom_root / "zh-CN" / "replyer.prompt").read_text(encoding="utf-8") == outdated_template


def test_missing_prompt_message_includes_name(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    with pytest.raises(FileNotFoundError) as exc_info:
        load_prompt("missing_template", prompts_root=tmp_path)

    assert "missing_template" in str(exc_info.value)
    assert not caplog.records


def test_load_prompt_rejects_path_traversal(tmp_path: Path) -> None:
    prompts_root = tmp_path / "prompts"
    write_prompt(prompts_root / "zh-CN", "replyer", "你好")

    with pytest.raises(ValueError):
        load_prompt("../replyer", prompts_root=prompts_root)


def test_list_prompt_templates_loads_directory_metadata(tmp_path: Path) -> None:
    prompts_root = tmp_path / "prompts"
    write_prompt(prompts_root / "zh-CN", "replyer", "中文")
    metadata_path = prompts_root / "zh-CN" / ".meta.toml"
    metadata_path.write_text(
        """
[replyer]
display_name = "回复器"
advanced = true
description = "用于生成回复的主模板"
""".strip(),
        encoding="utf-8",
    )

    prompt_templates = list_prompt_templates(prompts_root=prompts_root)
    metadata = prompt_templates["replyer"].metadata

    assert metadata.display_name == "回复器"
    assert metadata.advanced is True
    assert metadata.description == "用于生成回复的主模板"


def test_shared_metadata_parsed_once_per_scan_and_refreshed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompts_root = tmp_path / "prompts"
    write_prompt(prompts_root / "zh-CN", "replyer", "reply")
    write_prompt(prompts_root / "zh-CN", "planner", "plan")
    metadata_path = prompts_root / "zh-CN" / ".meta.toml"
    metadata_path.write_text('[replyer]\ndisplay_name = "Before"\n[planner]\nadvanced = true\n', encoding="utf-8")
    parse_calls = 0
    original_parse = prompt_templates.parse_toml

    def counted_parse(content: str):
        nonlocal parse_calls
        parse_calls += 1
        return original_parse(content)

    monkeypatch.setattr(prompt_templates, "parse_toml", counted_parse)
    templates = list_prompt_templates(prompts_root=prompts_root)
    assert parse_calls == 1
    assert templates["replyer"].metadata.display_name == "Before"
    assert templates["planner"].metadata.advanced is True

    metadata_path.write_text('[replyer]\ndisplay_name = "After"\n', encoding="utf-8")
    templates = list_prompt_templates(prompts_root=prompts_root)
    assert parse_calls == 2
    assert templates["replyer"].metadata.display_name == "After"
    assert templates["planner"].metadata.advanced is False


def test_list_prompt_templates_loads_prompt_specific_metadata(tmp_path: Path) -> None:
    prompts_root = tmp_path / "prompts"
    write_prompt(prompts_root / "zh-CN", "replyer", "中文")
    metadata_path = prompts_root / "zh-CN" / "replyer.meta.json"
    metadata_path.write_text(
        '{"display_name": "Replyer", "advanced": false, "description": "Prompt specific metadata"}',
        encoding="utf-8",
    )

    prompt_templates = list_prompt_templates(prompts_root=prompts_root)
    metadata = prompt_templates["replyer"].metadata

    assert metadata.display_name == "Replyer"
    assert metadata.advanced is False
    assert metadata.description == "Prompt specific metadata"


def test_builtin_prompt_templates_have_intro_metadata() -> None:
    templates = list_prompt_templates()
    assert templates
    for name, template_info in templates.items():
        assert template_info.metadata.display_name, f"{name} 缺少 display_name 元信息"
        assert template_info.metadata.description, f"{name} 缺少 description 元信息"


def test_builtin_emoji_content_analysis_template() -> None:
    prompt_path = PROMPTS_ROOT / "zh-CN" / "emoji_content_analysis.prompt"
    assert prompt_path.is_file()
    assert extract_prompt_placeholders(prompt_path.read_text(encoding="utf-8")) == {"image_type"}
    template_info = list_prompt_templates()["emoji_content_analysis"]
    assert template_info.path == prompt_path
    assert template_info.metadata.advanced is True


def test_list_prompt_templates_reports_duplicate_name_with_custom_root(tmp_path: Path) -> None:
    prompts_root = tmp_path / "prompts"
    first_dir = prompts_root / "zh-CN" / "chat"
    second_dir = prompts_root / "zh-CN" / "system"
    first_dir.mkdir(parents=True, exist_ok=True)
    second_dir.mkdir(parents=True, exist_ok=True)
    (first_dir / "replyer.prompt").write_text("chat", encoding="utf-8")
    (second_dir / "replyer.prompt").write_text("system", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        list_prompt_templates(prompts_root=prompts_root)

    assert "zh-CN/chat/replyer.prompt" in str(exc_info.value)
    assert "zh-CN/system/replyer.prompt" in str(exc_info.value)


def test_prompt_manager_loads_chinese_templates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts_root = tmp_path / "prompts"
    custom_prompts_root = tmp_path / "data" / "custom_prompts"
    custom_prompts_root.mkdir(parents=True, exist_ok=True)
    write_prompt(prompts_root / "zh-CN", "replyer", "中文模板")

    monkeypatch.setattr("src.prompt.prompt_manager.PROMPTS_DIR", prompts_root, raising=False)
    monkeypatch.setattr("src.prompt.prompt_manager.CUSTOM_PROMPTS_DIR", custom_prompts_root, raising=False)
    monkeypatch.setattr("src.prompt.prompt_manager.SUFFIX_PROMPT", ".prompt", raising=False)

    manager = PromptManager()
    manager.load_prompts()

    assert manager.get_prompt("replyer").template == "中文模板"
