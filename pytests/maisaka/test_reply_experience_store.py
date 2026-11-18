from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from src.learners import reply_experience_store
from src.learners.reply_experience_store import ReplyExperience, ReplyExperienceStore


def test_experience_store_persists_and_isolates_scope(tmp_path: Path) -> None:
    path = tmp_path / "data" / "reply_experiences.json"
    store = ReplyExperienceStore(path)
    experience = ReplyExperience("对方问截止时间", "先给日期", "修订稿直接给出了日期")

    assert store.list_for("chat", "user", "persona") == []
    store.remember("chat", "user", "persona", experience)

    reopened = ReplyExperienceStore(path)
    assert reopened.list_for("chat", "user", "persona") == [experience]
    assert reopened.list_for("another_chat", "user", "persona") == []
    assert reopened.list_for("chat", "another_user", "persona") == []
    assert reopened.list_for("chat", "user", "another_persona") == []


def test_experience_store_keeps_recent_entries_and_updates_the_same_cue(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(reply_experience_store, "_MAX_TOTAL", 6)
    store = ReplyExperienceStore(tmp_path / "reply_experiences.json")
    experiences = [ReplyExperience(f"情景 {i}", f"经验 {i}", f"证据 {i}") for i in range(6)]
    other = ReplyExperience("另一个会话", "使用不同经验", "另一条证据")
    store.remember("other_chat", "user", "persona", other)
    for experience in experiences:
        store.remember("chat", "user", "persona", experience)

    updated = ReplyExperience(experiences[1].cue, "修订后的经验", "更近期的证据")
    store.remember("chat", "user", "persona", updated)
    assert store.list_for("chat", "user", "persona") == [updated, *reversed(experiences[2:])]
    assert store.list_for("other_chat", "user", "persona") == [other]

    store.remember("third_chat", "user", "persona", other)
    assert store.list_for("other_chat", "user", "persona") == []


def test_experience_store_serializes_concurrent_writes(tmp_path: Path) -> None:
    store = ReplyExperienceStore(tmp_path / "reply_experiences.json")

    def remember(index: int) -> None:
        store.remember("chat", str(index), "persona", ReplyExperience("情景", "经验", str(index)))

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(remember, range(12)))

    for index in range(12):
        assert store.list_for("chat", str(index), "persona") == [ReplyExperience("情景", "经验", str(index))]


def test_experience_store_preserves_invalid_file(tmp_path: Path) -> None:
    path = tmp_path / "reply_experiences.json"
    path.write_text('{"experiences": [{}]}', encoding="utf-8")

    with pytest.raises(ValueError, match="回复经验文件格式无效"):
        ReplyExperienceStore(path).remember("chat", "user", "persona", ReplyExperience("情景", "经验", "证据"))

    assert path.read_text(encoding="utf-8") == '{"experiences": [{}]}'
