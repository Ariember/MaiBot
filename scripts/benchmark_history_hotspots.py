"""比较聊天文本、工具轮次定位和日志目录统计的 Git 基线与工作区性能。"""

from abc import ABC, abstractmethod
from argparse import ArgumentParser
from dataclasses import field
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

import json
import os
import platform
import sys
import uuid

from benchmark_runtime_hotspots import ROOT, compare, git, load_symbols


HISTORY_PATH = "src/maisaka/context/history.py"
SYSTEM_PATH = "src/webui/routers/system.py"


def history_scenarios(sources: Dict[str, str]) -> List[Dict[str, Any]]:
    from src.common.data_models.message_component_data_model import (
        AtComponent,
        DictComponent,
        EmojiComponent,
        ForwardComponent,
        ForwardNodeComponent,
        ImageComponent,
        MessageSequence,
        ReplyComponent,
        TextComponent,
        VoiceComponent,
    )
    from src.llm_models.payload_content import context_item
    from src.llm_models.payload_content.tool_option import ToolCall
    from src.maisaka.context.message_adapter import (
        build_visible_text_from_sequence,
        clone_message_sequence,
        format_speaker_content,
    )

    class_names = ["LLMContextMessage", "ContentContextMessage", "ModelOutputContextMessage", "ToolResultMessage"]
    context_globals = {name: value for name, value in vars(context_item).items() if not name.startswith("_")}
    message_classes = load_symbols(
        (ROOT / "src/maisaka/context/messages.py").read_text(encoding="utf-8"),
        class_names,
        "benchmark_history_messages",
        {
            **context_globals,
            "ABC": ABC,
            "abstractmethod": abstractmethod,
            "field": field,
            "uuid": uuid,
            "MessageSequence": MessageSequence,
            "ToolCall": ToolCall,
        },
    )
    modules = {
        variant: load_symbols(
            source,
            ["build_session_message_visible_text", "collect_tool_turn_anchor_indices", "_get_logical_turn_id"],
            f"benchmark_history_{variant}",
            {
                **{name: message_classes[name] for name in class_names},
                "MessageSequence": MessageSequence,
                "ReplyComponent": ReplyComponent,
                "RoleType": context_item.RoleType,
                "build_visible_text_from_sequence": build_visible_text_from_sequence,
                "clone_message_sequence": clone_message_sequence,
                "format_speaker_content": format_speaker_content,
            },
        )
        for variant, source in sources.items()
    }
    timestamp = datetime(2026, 11, 17, 12)
    normal = MessageSequence([TextComponent("今天下午讨论项目进度，稍后整理结果。")])
    mixed = MessageSequence(
        [
            ReplyComponent("reply-1", target_message_content="引用原文"),
            TextComponent("正文"),
            AtComponent("target", target_user_cardname="目标"),
            ImageComponent(binary_hash="image", content=" 图片描述 "),
            EmojiComponent(binary_hash="emoji"),
            VoiceComponent(binary_hash="voice", content=" 语音 "),
            DictComponent({"type": "custom", "data": [1, 2]}),
        ]
    )
    forwarded = MessageSequence(
        [
            *mixed.components,
            ForwardNodeComponent(
                [
                    ForwardComponent(
                        "转发用户",
                        f"forward-{index}",
                        [
                            TextComponent(f"转发内容 {index}"),
                            ForwardNodeComponent(
                                [
                                    ForwardComponent(
                                        "嵌套用户",
                                        f"nested-{index}-{child}",
                                        [
                                            TextComponent("嵌套正文" * 20),
                                            ImageComponent(
                                                binary_hash=f"image-{index}-{child}", content="合成图片描述"
                                            ),
                                        ],
                                    )
                                    for child in range(10)
                                ]
                            ),
                        ],
                    )
                    for index in range(40)
                ]
            ),
        ]
    )
    results = []
    for name, sequence, batch_size in (("plain", normal, 200), ("mixed", mixed, 200), ("forward_tree", forwarded, 20)):
        message = SimpleNamespace(
            raw_message=sequence,
            message_info=SimpleNamespace(
                user_info=SimpleNamespace(
                    user_cardname="群名片",
                    user_nickname="昵称",
                    user_id="user-1",
                )
            ),
            timestamp=timestamp,
            message_id="message-1",
            is_notify=False,
        )

        def render(module, message=message, batch_size=batch_size):
            return [module["build_session_message_visible_text"](message) for _ in range(batch_size)]

        results.append(
            {
                "scenario": "visible_message_text",
                "message_kind": name,
                "calls_per_sample": batch_size,
                "top_level_components": len(sequence.components),
                "forward_messages": 440 if name == "forward_tree" else 0,
                **compare(lambda: render(modules["before"]), lambda: render(modules["after"]), lambda result: result),
            }
        )

    for pattern, turns in (("no_tools", 20), ("alternating", 20), ("consecutive", 20), ("consecutive", 500)):
        history = [message_classes["ContentContextMessage"](normal, "用户上下文", timestamp)]
        turn_ids = set() if pattern == "no_tools" else {f"turn-{index}" for index in range(turns)}
        for index in range(turns):
            if pattern == "no_tools":
                history.append(message_classes["ContentContextMessage"](normal, "用户上下文", timestamp))
                continue
            if pattern == "alternating" and index > 0:
                history.append(message_classes["ContentContextMessage"](normal, "用户上下文", timestamp))
            turn_id, call_id = f"turn-{index}", f"call-{index}"
            history.append(
                message_classes["ModelOutputContextMessage"](
                    context_item.FunctionCallItem(
                        meta=context_item.ContextItemMeta(f"item-{index}", turn_id, timestamp),
                        tool_call=context_item.ContextToolCall.create(call_id=call_id, func_name="query_memory"),
                    )
                )
            )
            history.append(message_classes["ToolResultMessage"]("合成查询结果", timestamp, call_id, turn_id))
        results.append(
            {
                "scenario": "tool_turn_anchors",
                "history_pattern": pattern,
                "logical_turns": len(turn_ids),
                "history_messages": len(history),
                "user_messages": turns + 1 if pattern == "no_tools" else turns if pattern == "alternating" else 1,
                **compare(
                    partial(modules["before"]["collect_tool_turn_anchor_indices"], history, turn_ids),
                    partial(modules["after"]["collect_tool_turn_anchor_indices"], history, turn_ids),
                    lambda result: result,
                ),
            }
        )
    return results


def log_directory_scenario(sources: Dict[str, str]) -> Dict[str, Any]:
    with TemporaryDirectory(prefix="maibot-log-benchmark-") as directory:
        log_dir = Path(directory) / "logs"
        log_dir.mkdir()
        (log_dir / "app.log").write_bytes(b"root log\n")
        (log_dir / "empty").mkdir()
        chats, files_per_chat, file_bytes = 100, 5, 1024
        for task in ("planner", "replyer"):
            for chat in range(chats):
                chat_dir = log_dir / "maisaka_prompt" / task / f"chat-{chat:03d}"
                chat_dir.mkdir(parents=True)
                for index in range(files_per_chat):
                    (chat_dir / f"request-{index}.json").write_bytes(b"x" * file_bytes)
        modules = {
            variant: load_symbols(
                source,
                ["LocalCacheLogDirectoryItem", "_get_files_stats", "_iter_files", "_build_log_directory_items"],
                f"benchmark_log_directories_{variant}",
                {"Path": Path, "os": os, "Tuple": Tuple, "_LOG_DIR": log_dir},
            )
            for variant, source in sources.items()
        }
        return {
            "scenario": "log_directory_statistics",
            "chats_per_task": chats,
            "tasks": 2,
            "files_per_chat": files_per_chat,
            "file_bytes": file_bytes,
            "total_files": 2 * chats * files_per_chat + 1,
            "directories_including_root": 2 * chats + 5,
            "layout": "logs/maisaka_prompt/{planner,replyer}/{chat}; root file and empty directory",
            **compare(
                modules["before"]["_build_log_directory_items"],
                modules["after"]["_build_log_directory_items"],
                lambda result: [item.model_dump() for item in result],
            ),
        }


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref", required=True, help="优化前的 Git 提交或引用")
    parser.add_argument("--output", type=Path, help="JSON 报告路径")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    baseline = git("rev-parse", "--verify", f"{args.baseline_ref}^{{commit}}")
    sources = {
        path: {"before": git("show", f"{baseline}:{path}"), "after": (ROOT / path).read_text(encoding="utf-8")}
        for path in (HISTORY_PATH, SYSTEM_PATH)
    }
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_sha": baseline,
        "working_tree_head": git("rev-parse", "HEAD"),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "method": {
            "warmup_rounds": 2,
            "measurement_rounds": 9,
            "order": "alternating AB/BA",
            "timing": "warm-cache median via perf_counter; output serialization/equality excluded",
            "memory": "separate tracemalloc peak; Python allocations only; excludes native and filesystem caches",
            "scope": "AST-extracted actual functions/classes; same synthetic inputs; temporary log tree",
            "visible_text_scope": "actual components/renderers; session scalar fields supplied by SimpleNamespace",
            "forward_scope": "visible-text renderer already skips forward nodes; deep copying their tree is unnecessary",
            "anchor_scope": "actual context classes/role properties; no tools, alternating user/tool turns, consecutive tools",
            "isolation": "no production database/config imports or external model requests",
        },
        "limitations": [
            "Synthetic data and warm caches; not an end-to-end measurement of live platforms or model providers.",
            "Memory is peak Python allocation during each call, not process RSS or total retained application memory.",
        ],
        "results": [*history_scenarios(sources[HISTORY_PATH]), log_directory_scenario(sources[SYSTEM_PATH])],
    }
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
