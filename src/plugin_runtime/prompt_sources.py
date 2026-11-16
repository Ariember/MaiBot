"""提取插件对提示词文本的改动，供请求预览展示来源。"""

from typing import Any, Dict, List, Tuple


PROMPT_SOURCE_HOOKS = {
    "maisaka.planner.before_request",
    "maisaka.replyer.before_request",
    "maisaka.replyer.before_model_request",
}


def _item_texts(items: Any) -> Dict[str, Tuple[str, str]]:
    texts: Dict[str, Tuple[str, str]] = {}
    if not isinstance(items, list):
        return texts
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not isinstance(item.get("parts"), list):
            continue
        meta = item.get("meta")
        item_id = str(meta.get("item_id", "")) if isinstance(meta, dict) else ""
        text = "\n".join(
            part["text"]
            for part in item["parts"]
            if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str)
        )
        texts[item_id or str(index)] = (f"items[{index}]", text)
    return texts


def collect_prompt_changes(
    before: Dict[str, Any], after: Dict[str, Any], *, source: str, hook: str
) -> List[Dict[str, str]]:
    """按处理器记录追加、替换与删除；不复制图片或改变插件载荷。"""
    changes: List[Dict[str, str]] = []

    def record(target: str, previous: str, current: str, item_id: str = "") -> None:
        if previous == current:
            return
        if not current:
            operation, text = "remove", previous
        elif current.startswith(previous):
            operation, text = "append", current[len(previous):]
        else:
            operation, text = "replace", current
        entry = {"source": source, "hook": hook, "target": target, "operation": operation, "text": text}
        if item_id:
            entry["item_id"] = item_id
        changes.append(entry)

    if hook == "maisaka.replyer.before_request":
        record("extra_prompt", str(before.get("extra_prompt") or ""), str(after.get("extra_prompt") or ""))

    if hook in {"maisaka.planner.before_request", "maisaka.replyer.before_model_request"} and isinstance(after.get("items"), list):
        previous_items = _item_texts(before.get("items"))
        current_items = _item_texts(after["items"])
        for item_id, (target, current) in current_items.items():
            record(target, previous_items.get(item_id, ("", ""))[1], current, item_id)
        for item_id, (target, previous) in previous_items.items():
            if item_id not in current_items:
                record(target, previous, "", item_id)

    previous_args = before.get("reply_tool_args")
    current_args = after.get("reply_tool_args")
    if hook == "maisaka.replyer.before_request" and isinstance(previous_args, dict) and isinstance(current_args, dict):
        for name in ("reply_reference", "reply_style"):
            previous, current = previous_args.get(name, ""), current_args.get(name, "")
            if isinstance(previous, str) and isinstance(current, str):
                record(f"reply_tool_args.{name}", previous, current)
        previous = previous_args.get("persona_expressions", [])
        current = current_args.get("persona_expressions", [])
        if (
            isinstance(previous, list) and isinstance(current, list)
            and all(isinstance(item, str) for item in previous + current)
        ):
            record("reply_tool_args.persona_expressions", "\n\n".join(previous), "\n\n".join(current))
    return changes
