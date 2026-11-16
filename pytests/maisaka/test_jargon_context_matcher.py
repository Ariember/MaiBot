from contextlib import contextmanager
from dataclasses import asdict

from sqlalchemy import event
from sqlmodel import Session, create_engine

import pytest


@pytest.fixture(scope="module")
def matcher_module(tmp_path_factory):
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("MAIBOT_INSTANCE_DIR", str(tmp_path_factory.mktemp("jargon-instance")))
        from src.maisaka import jargon_context_matcher

        yield jargon_context_matcher


@pytest.mark.parametrize("limit", [0, 1, 3, 10])
def test_jargon_matching_preserves_normalization_priority_and_order(matcher_module, monkeypatch, limit):
    candidates = [
        matcher_module._JargonCandidate(content, meaning, count, True, "{}")
        for content, meaning, count in [
            (" Foo \tBar ", "优先释义", 100),
            ("foo bar", "重复释义", 99),
            ("甲", "短词", 20),
            ("甲乙", "长词乙", 20),
            ("甲丙", "长词丙", 20),
            ("高频", "高频释义", 3),
            ("未命中", "其他释义", 2),
            (" \t ", "空词", 1),
        ]
    ]
    monkeypatch.setattr(matcher_module, "_extract_other_user_texts", lambda _messages: [
        "FOO \nBAR 甲乙 甲丙 甲", "foo bar 高频",
    ])
    monkeypatch.setattr(matcher_module, "_load_scoped_jargon_candidates", lambda _session_id: candidates)
    monkeypatch.setattr(matcher_module, "_load_high_frequency_terms", lambda _session_id: {
        "高频": matcher_module._HighFrequencyTermSummary("高频", 1, 8),
    })

    matches = matcher_module.match_jargons_for_context(session_id="chat", context_messages=[], limit=limit)

    expected = [
        ("高频", "高频释义", 1, 1117.99),
        (" Foo \tBar ", "优先释义", 0, 100.0),
        ("甲丙", "长词丙", 0, 20.0),
        ("甲乙", "长词乙", 0, 20.0),
        ("甲", "短词", 0, 20.0),
    ][:max(1, limit)]
    assert [asdict(match) for match in matches] == [
        {
            "content": content,
            "meaning": meaning,
            "score": score,
            "first_message_index": index,
            "jargon_count": 3 if content == "高频" else 100 if content == " Foo \tBar " else 20,
            "high_frequency_term": "高频" if content == "高频" else "",
            "high_frequency_rank": 1 if content == "高频" else 0,
            "high_frequency_count": 8 if content == "高频" else 0,
        }
        for content, meaning, index, score in expected
    ]


def test_jargon_matching_uses_updated_candidates_on_each_call(matcher_module, monkeypatch):
    candidate = matcher_module._JargonCandidate("原词", "释义", 1, True, "{}")
    monkeypatch.setattr(matcher_module, "_extract_other_user_texts", lambda _messages: ["新词"])
    monkeypatch.setattr(matcher_module, "_load_scoped_jargon_candidates", lambda _session_id: [candidate])
    monkeypatch.setattr(matcher_module, "_load_high_frequency_terms", lambda _session_id: {})

    assert matcher_module.match_jargons_for_context(session_id="chat", context_messages=[]) == []
    candidate.content = "新词"
    matches = matcher_module.match_jargons_for_context(session_id="chat", context_messages=[])

    assert [match.content for match in matches] == ["新词"]


@pytest.mark.parametrize("texts,first_index", [
    ([], None),
    (["", " \t "], None),
    (["没有相关内容", "其他文字"], None),
    (["", " \t ", "第一次命中关键词", "关键词再次出现"], 2),
])
def test_jargon_matching_preserves_empty_message_positions(matcher_module, monkeypatch, texts, first_index):
    candidates = [
        matcher_module._JargonCandidate("关键词", "首个释义", 7, True, "{}"),
        matcher_module._JargonCandidate(" 关键词 ", "重复释义", 99, True, "{}"),
        matcher_module._JargonCandidate(" \t ", "空词", 100, True, "{}"),
    ]
    monkeypatch.setattr(matcher_module, "_extract_other_user_texts", lambda _messages: texts)
    monkeypatch.setattr(matcher_module, "_load_scoped_jargon_candidates", lambda _session_id: candidates)
    monkeypatch.setattr(matcher_module, "_load_high_frequency_terms", lambda _session_id: {})

    matches = matcher_module.match_jargons_for_context(session_id="chat", context_messages=[])

    expected = [] if first_index is None else [
        matcher_module._JargonMatch("关键词", "首个释义", 7 - first_index * 0.01, first_index, 7, "", 0, 0),
    ]
    assert matches == expected


def test_scoped_jargon_projection_preserves_filtering_and_order(matcher_module, monkeypatch):
    engine = create_engine("sqlite://")
    jargon_model = matcher_module.Jargon
    jargon_model.__table__.create(engine)
    records = [
        (" 全局词 ", " 全局释义 ", 50, True, "invalid", True),
        ("同词", "当前聊天释义", 30, False, '{"chat":1}', True),
        ("同词", "关联聊天释义", 30, False, '{"related":1}', True),
        ("其他聊天", "释义", 100, False, '{"other":1}', True),
        ("损坏归属", "释义", 100, False, "invalid", True),
        ("非字典归属", "释义", 100, False, "[]", True),
        (" \t ", "释义", 100, True, "{}", True),
        ("空释义", "", 100, True, "{}", True),
        ("空白释义", " \t ", 100, True, "{}", True),
        ("非黑话", "释义", 100, True, "{}", False),
        ("待判定", "释义", 100, True, "{}", None),
    ]
    with Session(engine) as session:
        session.add_all([
            jargon_model(
                id=index,
                content=content,
                meaning=meaning,
                count=count,
                is_global=is_global,
                session_id_dict=scope,
                is_jargon=is_jargon,
                evidence_messages="evidence" * 1000,
            )
            for index, (content, meaning, count, is_global, scope, is_jargon) in enumerate(records, start=1)
        ])
        session.commit()

    statements = []

    @event.listens_for(engine, "before_cursor_execute")
    def capture_statement(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    @contextmanager
    def get_db_session(*, auto_commit=False):
        with Session(engine) as session:
            yield session

    monkeypatch.setattr(matcher_module, "get_db_session", get_db_session)
    monkeypatch.setattr(
        matcher_module.JargonConfigUtils,
        "resolve_jargon_group_scope",
        lambda _session_id: ({"chat", "related"}, None),
    )
    try:
        candidates = matcher_module._load_scoped_jargon_candidates("chat")
        assert candidates == [
            matcher_module._JargonCandidate("全局词", "全局释义", 50, True, "invalid"),
            matcher_module._JargonCandidate("同词", "关联聊天释义", 30, False, '{"related":1}'),
            matcher_module._JargonCandidate("同词", "当前聊天释义", 30, False, '{"chat":1}'),
        ]
        assert len(statements) == 1
        assert "evidence_messages" not in statements[0]
    finally:
        engine.dispose()
