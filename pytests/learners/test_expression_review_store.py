from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import List

from src.learners import expression_review_store


def test_concurrent_appends_and_reads_keep_all_entries(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(expression_review_store, "REVIEW_LOG_PATH", tmp_path / "review_logs.json")
    start = Barrier(3)

    def write_and_read(worker: int) -> List[str]:
        start.wait()
        written_ids = []
        for index in range(12):
            entry = expression_review_store.append_ai_review_log(
                session_id=f"session-{worker}",
                situation=f"情景{index}",
                style=f"表达{index}",
                passed=True,
                reason="审核通过",
                source="auto",
            )
            written_ids.append(entry["id"])
            assert any(item["id"] == entry["id"] for item in expression_review_store.read_review_log_entries())
        return written_ids

    with ThreadPoolExecutor(max_workers=3) as executor:
        written_ids = [entry_id for ids in executor.map(write_and_read, range(3)) for entry_id in ids]

    entries = expression_review_store.read_review_log_entries()
    assert len(entries) == len(written_ids) == 36
    assert {entry["id"] for entry in entries} == set(written_ids)
