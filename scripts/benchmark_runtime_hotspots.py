"""用合成人物和聊天数据比较指定 Git 基线与工作区的查询、黑话匹配性能。"""

from argparse import ArgumentParser
from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from importlib.metadata import version
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter
from types import ModuleType
from typing import Any, Callable, Dict, List, Optional, Sequence

from fastapi import HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Float, Index, case, event, func
from sqlmodel import Field, LargeBinary, Session, SQLModel, col, create_engine, select

import ast
import gc
import json
import logging
import platform
import sqlite3
import subprocess
import sys
import tracemalloc


ROOT = Path(__file__).resolve().parents[1]
PERSON_PATH = "src/webui/routers/person.py"
JARGON_PATH = "src/maisaka/jargon_context_matcher.py"
DATABASE_PATH = "src/common/database/database.py"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT).decode("utf-8").strip()


def load_symbols(
    source: str, names: Sequence[str], label: str, injected: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    # 仅执行实际定义，跳过业务模块导入、配置初始化和路由注册。
    nodes = [
        node
        for node in ast.parse(source).body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names
    ]
    missing = set(names) - {node.name for node in nodes}
    if missing:
        raise ValueError(f"{label} 缺少基准所需定义: {sorted(missing)}")
    for node in nodes:
        if isinstance(node, ast.FunctionDef):
            node.decorator_list = []
    module = ModuleType(label)
    module.__dict__.update(
        Any=Any,
        Dict=Dict,
        List=List,
        Optional=Optional,
        Sequence=Sequence,
        datetime=datetime,
        BaseModel=BaseModel,
        SQLModel=SQLModel,
        Field=Field,
        Column=Column,
        DateTime=DateTime,
        Float=Float,
        Index=Index,
        LargeBinary=LargeBinary,
        col=col,
        select=select,
        case=case,
        func=func,
        Query=Query,
        HTTPException=HTTPException,
        json=json,
        dataclass=dataclass,
        LLMContextMessage=object,
        MAX_JARGON_REFERENCE_MATCHES=10,
        logger=logging.getLogger(label),
    )
    module.__dict__.update(injected or {})
    sys.modules[label] = module
    exec(compile(ast.Module(body=nodes, type_ignores=[]), label, "exec", dont_inherit=True), module.__dict__)
    return module.__dict__


def compare(before: Callable, after: Callable, serialize: Callable) -> Dict[str, Any]:
    functions = {"before": before, "after": after}
    expected = None
    for _ in range(2):
        expected = serialize(before())
        assert serialize(after()) == expected, "预热阶段输出不一致"
    samples = {"before": [], "after": []}
    for iteration in range(9):
        order = ("before", "after") if iteration % 2 == 0 else ("after", "before")
        for name in order:
            started = perf_counter()
            result = functions[name]()
            samples[name].append((perf_counter() - started) * 1000)
            assert serialize(result) == expected, f"{name} 第 {iteration + 1} 轮输出不一致"
    peaks = {}
    for name, function in functions.items():
        gc.collect()
        tracemalloc.start()
        try:
            result = function()
            peaks[name] = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        assert serialize(result) == expected, f"{name} 内存测量输出不一致"
    results = {
        name: {"median_ms": median(values), "samples_ms": values, "peak_python_bytes": peaks[name]}
        for name, values in samples.items()
    }
    return {**results, "speedup": results["before"]["median_ms"] / results["after"]["median_ms"], "outputs_equal": True}


def person_scenarios(sources: Dict[str, str], configure: Callable) -> List[Dict[str, Any]]:
    model_source = (ROOT / "src/common/database/database_model.py").read_text(encoding="utf-8")
    person_model = load_symbols(model_source, ["PersonInfo"], "benchmark_person_model")["PersonInfo"]
    names = [
        "PersonInfoResponse",
        "PersonListResponse",
        "parse_group_nick_name",
        "person_to_response",
        "get_person_list",
        "get_person_stats",
    ]
    modules = {}
    for variant, source in sources.items():
        modules[variant] = load_symbols(source, names, f"benchmark_person_{variant}", {"PersonInfo": person_model})
    results = []
    list_params = {"page": 1, "page_size": 20, "search": None, "is_known": None, "platform": None, "user_id": None}
    for count in (10_000, 100_000):
        engine = create_engine("sqlite://")
        event.listen(engine, "connect", configure)
        person_model.__table__.create(engine)

        @contextmanager
        def db_session(bind=engine):
            with Session(bind, expire_on_commit=False) as session:
                yield session
                session.commit()

        try:
            start = datetime(2026, 1, 1)
            rows = [
                {
                    "person_id": f"person-{index}",
                    "platform": ("qq", "discord", "telegram", "")[index % 4],
                    "user_id": str(index),
                    "user_nickname": f"昵称{index}",
                    "is_known": index % 3 == 0,
                    "person_name": None if index % 5 == 0 else f"人物{index}",
                    "last_known_time": None if index % 7 == 0 else start + timedelta(seconds=index),
                }
                for index in range(count)
            ]
            with engine.begin() as connection:
                connection.execute(person_model.__table__.insert(), rows)
            del rows
            for module in modules.values():
                module["get_db_session"] = db_session
            results.append(
                {
                    "scenario": "person_list",
                    "people": count,
                    "page_size": 20,
                    **compare(
                        lambda: modules["before"]["get_person_list"](**list_params),
                        lambda: modules["after"]["get_person_list"](**list_params),
                        lambda result: result.model_dump(),
                    ),
                }
            )
            results.append(
                {
                    "scenario": "person_stats",
                    "people": count,
                    **compare(
                        modules["before"]["get_person_stats"],
                        modules["after"]["get_person_stats"],
                        lambda result: result,
                    ),
                }
            )
        finally:
            engine.dispose()
    return results


def jargon_scenario(sources: Dict[str, str]) -> Dict[str, Any]:
    names = [
        "_JargonCandidate",
        "_JargonMatch",
        "_HighFrequencyTermSummary",
        "match_jargons_for_context",
        "_normalize_match_text",
        "_contains_mechanical_match",
        "_calculate_match_score",
    ]
    modules = {
        variant: load_symbols(source, names, f"benchmark_jargon_{variant}") for variant, source in sources.items()
    }
    texts = [f"今天讨论 TERM {index:04d}，还有 term {(index * 17) % 2980:04d}。" for index in range(50)]
    for module in modules.values():
        candidates = [
            module["_JargonCandidate"](f"Term {index:04d}", f"含义{index}", 3000 - index, True, "{}")
            for index in range(2980)
        ]
        candidates.extend(
            module["_JargonCandidate"](f"  TERM\t{index:04d}  ", "重复含义", 1, True, "{}") for index in range(20)
        )
        terms = {
            f"term {index:04d}": module["_HighFrequencyTermSummary"](f"Term {index:04d}", index + 1, 100)
            for index in range(30)
        }
        module["_extract_other_user_texts"] = lambda messages: messages
        module["_load_scoped_jargon_candidates"] = lambda session_id, values=candidates: values
        module["_load_high_frequency_terms"] = lambda session_id, values=terms: values
    return {
        "scenario": "jargon_matching",
        "messages": len(texts),
        "candidates": 3000,
        "duplicate_candidates": 20,
        "high_frequency_terms": 30,
        "limit": 10,
        **compare(
            lambda: modules["before"]["match_jargons_for_context"](session_id="synthetic", context_messages=texts),
            lambda: modules["after"]["match_jargons_for_context"](session_id="synthetic", context_messages=texts),
            lambda result: [asdict(item) for item in result],
        ),
    }


def reply_scenarios(sources: Dict[str, str], configure: Callable) -> List[Dict[str, Any]]:
    indexes = {}
    for variant, source in sources.items():
        node = next(
            node
            for node in ast.parse(source).body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "_RUNTIME_PERFORMANCE_INDEXES" for target in node.targets
            )
        )
        indexes[variant] = {
            name: ddl for name, ddl in ast.literal_eval(node.value) if name.startswith("ix_mai_messages_")
        }
    added = {name: ddl for name, ddl in indexes["after"].items() if name not in indexes["before"]}
    assert "ix_mai_messages_reply_to" in added, "基线与工作区必须包含待测 reply_to 索引差异"
    model_source = (ROOT / "src/common/database/database_model.py").read_text(encoding="utf-8")
    messages = load_symbols(model_source, ["Messages"], "benchmark_message_model")["Messages"]
    with TemporaryDirectory(prefix="maibot-benchmark-") as directory:
        before_path, after_path = (Path(directory) / name for name in ("before.db", "after.db"))
        before = create_engine(f"sqlite:///{before_path.as_posix()}")
        after = create_engine(f"sqlite:///{after_path.as_posix()}")
        event.listen(before, "connect", configure)
        event.listen(after, "connect", configure)
        try:
            messages.__table__.create(before)
            with before.begin() as connection:
                for ddl in indexes["before"].values():
                    connection.exec_driver_sql(ddl)
                for start in range(0, 200_000, 2000):
                    connection.execute(
                        messages.__table__.insert(),
                        [
                            {
                                "message_id": f"message-{index}",
                                "timestamp": datetime(2026, 1, 1),
                                "platform": "qq",
                                "user_id": str(index % 1000),
                                "user_nickname": "用户",
                                "session_id": f"session-{index % 100}",
                                "raw_content": b"x" * 256,
                                "reply_to": f"target-{index // 20}" if index % 10 == 0 else None,
                            }
                            for index in range(start, start + 2000)
                        ],
                    )
            with closing(sqlite3.connect(before_path)) as source, closing(sqlite3.connect(after_path)) as destination:
                source.backup(destination)
            with after.begin() as connection:
                page_size = connection.exec_driver_sql("PRAGMA page_size").scalar_one()
                bytes_before = connection.exec_driver_sql("PRAGMA page_count").scalar_one() * page_size
                started = perf_counter()
                for ddl in added.values():
                    connection.exec_driver_sql(ddl)
            index_ms = (perf_counter() - started) * 1000
            with after.connect() as connection:
                extra_bytes = connection.exec_driver_sql("PRAGMA page_count").scalar_one() * page_size - bytes_before

            def lookup(engine, target):
                with Session(engine) as session:
                    return session.exec(select(messages).filter_by(reply_to=target)).all()

            results = []
            for target, hits in (("target-absent", 0), ("target-4567", 2)):
                assert len(lookup(before, target)) == hits
                results.append(
                    {
                        "scenario": "reply_lookup",
                        "messages": 200_000,
                        "reply_fraction": 0.1,
                        "hits": hits,
                        "raw_content_bytes": 256,
                        "added_indexes": added,
                        "index_build_ms": index_ms,
                        "index_bytes": extra_bytes,
                        **compare(
                            lambda value=target: lookup(before, value),
                            lambda value=target: lookup(after, value),
                            lambda rows: [row.model_dump() for row in rows],
                        ),
                    }
                )
            return results
        finally:
            before.dispose()
            after.dispose()


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref", required=True, help="优化前的 Git 提交或引用")
    parser.add_argument("--output", type=Path, help="JSON 报告路径；省略时只输出到终端")
    args = parser.parse_args()
    baseline = git("rev-parse", "--verify", f"{args.baseline_ref}^{{commit}}")
    sources = {
        path: {"before": git("show", f"{baseline}:{path}"), "after": (ROOT / path).read_text(encoding="utf-8")}
        for path in (PERSON_PATH, JARGON_PATH, DATABASE_PATH)
    }
    configure = load_symbols(sources[DATABASE_PATH]["after"], ["set_sqlite_pragma"], "benchmark_sqlite_settings")[
        "set_sqlite_pragma"
    ]
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
            "timing": "warm-cache median via perf_counter; serialization and equality assertions excluded",
            "memory": "separate tracemalloc peak; Python allocations only, excludes SQLite native memory",
            "scope": "AST-extracted actual functions/classes; isolated SQLite; synthetic deterministic data",
            "sqlite_settings": "actual set_sqlite_pragma: WAL, cache_size=-64000, synchronous=NORMAL",
            "sqlite_storage": "person: memory; replies: temporary files (same seed database via SQLite backup)",
            "jargon_scope": "matching/scoring only; candidate loading and message extraction excluded",
        },
        "results": [
            *person_scenarios(sources[PERSON_PATH], configure),
            jargon_scenario(sources[JARGON_PATH]),
            *reply_scenarios(sources[DATABASE_PATH], configure),
        ],
    }
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
