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
    assert [(match.content, match.meaning, match.first_message_index) for match in matches] == [
        (content, meaning, index) for content, meaning, index, _score in expected
    ]
    assert [match.score for match in matches] == pytest.approx([score for *_fields, score in expected])
    assert matches[0].high_frequency_term == "高频"
    assert matches[0].high_frequency_rank == 1
    assert matches[0].high_frequency_count == 8


def test_jargon_matching_uses_updated_candidates_on_each_call(matcher_module, monkeypatch):
    candidate = matcher_module._JargonCandidate("原词", "释义", 1, True, "{}")
    monkeypatch.setattr(matcher_module, "_extract_other_user_texts", lambda _messages: ["新词"])
    monkeypatch.setattr(matcher_module, "_load_scoped_jargon_candidates", lambda _session_id: [candidate])
    monkeypatch.setattr(matcher_module, "_load_high_frequency_terms", lambda _session_id: {})

    assert matcher_module.match_jargons_for_context(session_id="chat", context_messages=[]) == []
    candidate.content = "新词"
    matches = matcher_module.match_jargons_for_context(session_id="chat", context_messages=[])

    assert [match.content for match in matches] == ["新词"]
