"""比较黑话匹配、候选读取和表达聊天列表的 Git 基线与工作区性能。"""

from argparse import ArgumentParser
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from importlib.metadata import version
from pathlib import Path
from statistics import median
from types import ModuleType, SimpleNamespace
from typing import Any, Callable, Dict, List
from unittest.mock import patch

from sqlalchemy import Enum as SQLEnum, String, Text, event
from sqlmodel import Session, create_engine

import ast
import asyncio
import json
import platform
import sqlite3
import sys
import time

from benchmark_runtime_hotspots import ROOT, compare, git, jargon_scenario, load_symbols


JARGON_PATH = "src/maisaka/jargon_context_matcher.py"
EXPRESSION_PATH = "src/webui/routers/expression.py"
CAPABILITY_PATH = "src/plugin_runtime/capabilities/data.py"


def message_loop_scenario(sources: Dict[str, str]) -> Dict[str, Any]:
    handlers = {}
    for variant, source in sources.items():
        node = next(
            item
            for item in ast.parse(source).body
            if isinstance(item, ast.ClassDef) and item.name == "RuntimeDataCapabilityMixin"
        )
        node.body = [
            item
            for item in node.body
            if isinstance(item, ast.AsyncFunctionDef) and item.name == "_cap_message_get_by_time"
        ]
        module = load_symbols(ast.unparse(node), [node.name], f"benchmark_message_{variant}", {"asyncio": asyncio})
        instance = module[node.name]()
        instance._serialize_messages = lambda messages, **_kwargs: messages
        handlers[variant] = instance._cap_message_get_by_time

    def query(**_kwargs):
        time.sleep(0.05)
        return []

    services = ModuleType("src.services")
    services.message_service = SimpleNamespace(get_messages_by_time=query)

    async def measure():
        samples = {name: [] for name in handlers}
        await asyncio.to_thread(lambda: None)
        for iteration in range(11):
            order = ("before", "after") if iteration % 2 == 0 else ("after", "before")
            for name in order:

                async def heartbeat():
                    started = time.perf_counter()
                    await asyncio.sleep(0.005)
                    return max(0.0, (time.perf_counter() - started - 0.005) * 1000)

                task = asyncio.create_task(heartbeat())
                await asyncio.sleep(0)
                result = await handlers[name]("benchmark", "message.get_by_time", {})
                assert result == {"success": True, "messages": []}
                delay = await task
                if iteration >= 2:
                    samples[name].append(delay)
        return samples

    with patch.dict(sys.modules, {"src": ModuleType("src"), "src.services": services}):
        samples = asyncio.run(measure())
    return {
        "scenario": "plugin_message_event_loop",
        "simulated_query_ms": 50,
        "heartbeat_interval_ms": 5,
        "outputs_equal": True,
        **{
            name: {"heartbeat_lateness_median_ms": median(values), "samples_ms": values}
            for name, values in samples.items()
        },
    }


def jargon_load_scenario(sources: Dict[str, str], models: Dict[str, Any], configure: Callable) -> Dict[str, Any]:
    jargon = models["Jargon"]
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", configure)
    jargon.__table__.create(engine)

    @contextmanager
    def db_session(**_kwargs):
        with Session(engine) as session:
            yield session

    modules = {
        variant: load_symbols(
            source,
            ["_JargonCandidate", "_load_scoped_jargon_candidates", "_jargon_in_scope"],
            f"benchmark_jargon_load_{variant}",
            {
                "Jargon": jargon,
                "get_db_session": db_session,
                "JargonConfigUtils": SimpleNamespace(resolve_jargon_group_scope=lambda _id: ({"chat"}, None)),
            },
        )
        for variant, source in sources.items()
    }
    count, evidence_bytes = 3000, 4096
    try:
        with engine.begin() as connection:
            connection.execute(
                jargon.__table__.insert(),
                [
                    {
                        "content": f"词语{index}",
                        "meaning": f"释义{index}",
                        "count": index % 100,
                        "is_jargon": True,
                        "is_global": index % 3 == 0,
                        "session_id_dict": json.dumps({"chat" if index % 3 == 1 else "other": 1}),
                        "evidence_messages": "x" * evidence_bytes,
                        "created_by": "AI",
                    }
                    for index in range(count)
                ],
            )
        return {
            "scenario": "jargon_candidate_loading",
            "candidates": count,
            "evidence_bytes_per_row": evidence_bytes,
            **compare(
                lambda: modules["before"]["_load_scoped_jargon_candidates"]("chat"),
                lambda: modules["after"]["_load_scoped_jargon_candidates"]("chat"),
                lambda result: [asdict(item) for item in result],
            ),
        }
    finally:
        engine.dispose()


def expression_scenarios(sources: Dict[str, str], models: Dict[str, Any], configure: Callable) -> List[Dict[str, Any]]:
    names = [
        "ChatInfo",
        "ChatListResponse",
        "is_current_account_session",
        "decode_expression_session_id",
        "get_expression_session_ids",
        "get_visible_expression_chat_ids",
        "build_chat_info",
        "get_chat_list",
    ]
    modules = {
        variant: load_symbols(
            source,
            names,
            f"benchmark_expression_{variant}",
            {
                **models,
                "LOGGED_INVALID_EXPRESSION_SESSION_IDS": set(),
                "get_configured_platform_accounts": lambda: {("qq", "bot")},
                "get_chat_name": lambda chat_id, _db: f"群聊{chat_id}",
                "ExpressionConfigUtils": SimpleNamespace(get_expression_config_for_chat=lambda _id: (True, False)),
            },
        )
        for variant, source in sources.items()
    }
    results = []
    for count in (100, 1000):
        engine = create_engine("sqlite://")
        event.listen(engine, "connect", configure)
        for name in ("ChatSession", "Expression", "Messages"):
            models[name].__table__.create(engine)

        @contextmanager
        def db_session(bind=engine):
            with Session(bind) as session:
                yield session
                session.commit()

        try:
            start = datetime(2026, 1, 1)
            with engine.begin() as connection:
                connection.execute(
                    models["ChatSession"].__table__.insert(),
                    [
                        {
                            "session_id": f"chat-{index}",
                            "platform": "qq",
                            "account_id": "bot",
                            "user_id": None,
                            "group_id": str(index),
                            "group_name": f"群聊{index}",
                        }
                        for index in range(count)
                    ],
                )
                connection.execute(
                    models["Expression"].__table__.insert(),
                    [
                        {"session_id": f"chat-{index}", "situation": "场景", "style": "表达", "content_list": "[]"}
                        for index in range(count)
                    ],
                )
                connection.execute(
                    models["Messages"].__table__.insert(),
                    [
                        {
                            "message_id": str(index),
                            "session_id": f"chat-{index}",
                            "platform": "qq",
                            "user_id": "user",
                            "user_nickname": "用户",
                            "raw_content": b"",
                            "timestamp": start + timedelta(seconds=index // 2),
                        }
                        for index in range(count)
                    ],
                )
            for module in modules.values():
                module["get_db_session"] = db_session
            query_counts = {}
            for variant, module in modules.items():
                statements = []

                def record_query(_conn, _cursor, statement, _parameters, _context, _executemany, captured=statements):
                    captured.append(statement)

                event.listen(engine, "before_cursor_execute", record_query)
                try:
                    module["get_chat_list"](include_legacy=False)
                finally:
                    event.remove(engine, "before_cursor_execute", record_query)
                query_counts[variant] = len(statements)
            results.append(
                {
                    "scenario": "expression_chat_list",
                    "chats": count,
                    "query_counts": query_counts,
                    **compare(
                        lambda: modules["before"]["get_chat_list"](include_legacy=False),
                        lambda: modules["after"]["get_chat_list"](include_legacy=False),
                        lambda result: result.model_dump(),
                    ),
                }
            )
        finally:
            engine.dispose()
    return results


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref", required=True, help="优化前的 Git 提交或引用")
    parser.add_argument("--output", type=Path, help="JSON 报告路径")
    args = parser.parse_args()
    baseline = git("rev-parse", "--verify", f"{args.baseline_ref}^{{commit}}")
    sources = {
        path: {"before": git("show", f"{baseline}:{path}"), "after": (ROOT / path).read_text(encoding="utf-8")}
        for path in (JARGON_PATH, EXPRESSION_PATH, CAPABILITY_PATH)
    }
    models = load_symbols(
        (ROOT / "src/common/database/database_model.py").read_text(encoding="utf-8"),
        ["ModifiedBy", "JargonCreatedBy", "Jargon", "ChatSession", "Expression", "Messages"],
        "benchmark_context_models",
        {"Enum": Enum, "SQLEnum": SQLEnum, "String": String, "Text": Text},
    )
    configure = load_symbols(
        (ROOT / "src/common/database/database.py").read_text(encoding="utf-8"),
        ["set_sqlite_pragma"],
        "benchmark_context_sqlite_settings",
    )["set_sqlite_pragma"]
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_sha": baseline,
        "working_tree_head": git("rev-parse", "HEAD"),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "sqlite": sqlite3.sqlite_version,
            **{name: version(name) for name in ("sqlmodel", "sqlalchemy", "pydantic", "fastapi")},
        },
        "method": {
            "warmup_rounds": 2,
            "measurement_rounds": 9,
            "order": "alternating AB/BA",
            "timing": "warm-cache median via perf_counter; output serialization/equality excluded",
            "memory": "separate tracemalloc peak; Python allocations only",
            "scope": "AST-extracted actual functions/classes; synthetic data; isolated in-memory SQLite",
            "sqlite_settings": "actual set_sqlite_pragma; no production database access",
            "expression_scope": "actual query/response functions; cached chat names and fixed config",
            "jargon_scope": "matching/scoring and candidate loading measured separately",
            "message_loop_scope": "actual get_by_time handler; simulated 50 ms synchronous query; empty serialization",
        },
        "results": [
            jargon_scenario(sources[JARGON_PATH]),
            jargon_load_scenario(sources[JARGON_PATH], models, configure),
            *expression_scenarios(sources[EXPRESSION_PATH], models, configure),
            message_loop_scenario(sources[CAPABILITY_PATH]),
        ],
    }
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
