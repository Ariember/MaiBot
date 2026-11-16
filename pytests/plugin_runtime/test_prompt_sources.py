from copy import deepcopy
from types import SimpleNamespace

import pytest

from src.config.config import global_config
from src.plugin_runtime.host.hook_dispatcher import HookDispatcher, HookDispatchResult, HookHandlerExecutionResult
from src.plugin_runtime.host.hook_spec_registry import HookSpec
from src.plugin_runtime.prompt_sources import collect_prompt_changes


def _item(item_id, text):
    return {"item_type": "SystemMessageItem", "meta": {"item_id": item_id}, "parts": [
        {"type": "text", "text": text}, {"type": "image", "image_base64": "image-data"},
    ]}


def test_prompt_changes_follow_item_identity_without_copying_history_or_images():
    before = {"items": [_item("system", "人格"), _item("history", "聊天记录"), _item("removed", "旧要求")]}
    after = {"items": [_item("history", "聊天记录"), _item("system", "人格\n新要求"), _item("new", "新背景")]}
    original = deepcopy(before)
    changes = collect_prompt_changes(before, after, source="test.plugin", hook="maisaka.planner.before_request")
    assert [(entry["operation"], entry["text"]) for entry in changes] == [
        ("append", "\n新要求"), ("append", "新背景"), ("remove", "旧要求"),
    ]
    assert changes[0]["item_id"] == "system" and changes[0]["target"] == "items[1]"
    assert before == original
    assert "image-data" not in str(changes)


def test_prompt_changes_distinguish_replacement_from_append_and_skip_non_text_fields():
    changes = collect_prompt_changes(
        {"extra_prompt": "先前要求", "reply_tool_args": {"persona_style": "活泼"}, "model_name": "a"},
        {"extra_prompt": "新要求", "reply_tool_args": {"persona_style": "平静"}, "model_name": "b"},
        source="test.plugin", hook="maisaka.replyer.before_request",
    )
    assert [(entry["target"], entry["operation"], entry["text"]) for entry in changes] == [
        ("extra_prompt", "replace", "新要求"), ("reply_tool_args.persona_style", "replace", "平静"),
    ]
    removed = collect_prompt_changes(
        {"extra_prompt": "前一个插件的要求"}, {}, source="p", hook="maisaka.replyer.before_request",
    )
    assert removed[0]["operation"] == "remove" and removed[0]["text"] == "前一个插件的要求"


@pytest.mark.parametrize("hook,expected", [
    ("maisaka.replyer.before_request", ["extra_prompt", "reply_tool_args.persona_style"]),
    ("maisaka.replyer.before_model_request", ["items[0]"]),
    ("maisaka.planner.before_request", ["items[0]"]),
])
def test_sources_only_include_fields_consumed_at_each_hook(hook, expected):
    changes = collect_prompt_changes(
        {"items": [], "extra_prompt": "", "reply_tool_args": {}},
        {"items": [_item("new", "实际提示词")], "extra_prompt": "补充", "reply_tool_args": {"persona_style": "活泼"}},
        source="test.plugin", hook=hook,
    )
    assert [change["target"] for change in changes] == expected


@pytest.mark.parametrize("record,allow,success,count", [
    (True, True, True, 1), (False, True, True, 0), (True, False, True, 0), (True, True, False, 0),
])
def test_dispatcher_records_only_accepted_prompt_mutations(monkeypatch, record, allow, success, count):
    monkeypatch.setattr(global_config.debug, "save_maisaka_reasoning", record)
    spec = HookSpec(name="maisaka.replyer.before_request", allow_kwargs_mutation=allow)
    target = SimpleNamespace(entry=SimpleNamespace(full_name="test.plugin.inject", error_policy="skip"))
    result = HookDispatchResult(hook_name=spec.name, kwargs={"extra_prompt": "基础"})
    execution = HookHandlerExecutionResult(
        handler_name="inject", plugin_id="test.plugin", success=success,
        modified_kwargs={"extra_prompt": "基础\n插件要求"},
    )
    HookDispatcher.__new__(HookDispatcher)._merge_blocking_result(spec, target, execution, result)
    assert len(result.prompt_sources) == count
    if count:
        assert result.prompt_sources[0]["source"] == "test.plugin.inject"
        assert result.prompt_sources[0]["text"] == "\n插件要求"
    assert result.kwargs["extra_prompt"] == ("基础\n插件要求" if allow and success else "基础")
