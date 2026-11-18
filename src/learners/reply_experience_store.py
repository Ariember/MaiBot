"""保存由回复重生成提炼的经验。"""

from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock
from typing import Dict, List, Tuple

from src.common.json_storage import read_json, write_json

_MAX_PER_SCOPE = 5
_MAX_TOTAL = 200
_RECORD_FIELDS = {"session_id", "user_id", "persona", "cue", "lesson", "evidence"}


@dataclass(frozen=True)
class ReplyExperience:
    cue: str
    lesson: str
    evidence: str


class ReplyExperienceStore:
    """按聊天流、回复对象和人设保存近期经验，最新记录排在前面。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()

    def list_for(self, session_id: str, user_id: str, persona: str) -> List[ReplyExperience]:
        scope = (session_id, user_id, persona)
        with self._lock:
            records = self._read_records()
        return [
            ReplyExperience(cue=record["cue"], lesson=record["lesson"], evidence=record["evidence"])
            for record in records
            if self._scope(record) == scope
        ][:_MAX_PER_SCOPE]

    def remember(self, session_id: str, user_id: str, persona: str, experience: ReplyExperience) -> None:
        scope = (session_id, user_id, persona)
        newest = {"session_id": session_id, "user_id": user_id, "persona": persona, **asdict(experience)}
        with self._lock:
            records = [newest]
            remaining_in_scope = _MAX_PER_SCOPE - 1
            for record in self._read_records():
                if self._scope(record) == scope:
                    if record["cue"] == experience.cue or remaining_in_scope == 0:
                        continue
                    remaining_in_scope -= 1
                records.append(record)
                if len(records) >= _MAX_TOTAL:
                    break
            self.path.parent.mkdir(parents=True, exist_ok=True)
            write_json(self.path, {"experiences": records})

    def _read_records(self) -> List[Dict[str, str]]:
        if not self.path.exists():
            return []
        payload = read_json(self.path)
        records = payload.get("experiences") if isinstance(payload, dict) else None
        if not isinstance(records, list) or any(
            not isinstance(record, dict)
            or record.keys() != _RECORD_FIELDS
            or any(not isinstance(value, str) for value in record.values())
            for record in records
        ):
            raise ValueError(f"回复经验文件格式无效：{self.path}")
        return records

    @staticmethod
    def _scope(record: Dict[str, str]) -> Tuple[str, str, str]:
        return record["session_id"], record["user_id"], record["persona"]
