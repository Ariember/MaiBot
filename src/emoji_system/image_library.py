"""本地图库索引，沿用 smart_imagechat 的 SQLite 格式。"""

from contextlib import closing
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, UnidentifiedImageError

import hashlib
import json
import re
import sqlite3


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
FORMAT_SUFFIXES = {"JPEG": ".jpg", "PNG": ".png", "GIF": ".gif", "WEBP": ".webp", "BMP": ".bmp"}


def normalize_tags(raw: Any) -> List[str]:
    if isinstance(raw, str):
        raw = re.split(r"[,\n，、；;\s]+", raw)
    if not isinstance(raw, list):
        return []
    return list(dict.fromkeys(tag.strip() for tag in raw if isinstance(tag, str) and tag.strip()))


class ImageLibrary:
    def __init__(self, data_dir: Path, max_bytes: int, max_images: int):
        self.root = data_dir.resolve()
        self.images = self.root / "images"
        self.images.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "library.sqlite3"
        self.max_bytes = max_bytes
        self.max_images = max_images
        with closing(self._connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS images (
                id TEXT PRIMARY KEY, filename TEXT NOT NULL, rel_path TEXT NOT NULL,
                manual_tags TEXT NOT NULL, auto_tags TEXT NOT NULL DEFAULT '[]',
                caption_status TEXT NOT NULL DEFAULT 'pending')""")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def add_bytes(
        self, data: bytes, filename: str, tags: Any = None, source: Optional[Path] = None
    ) -> Tuple[Dict[str, Any], bool]:
        if not data or len(data) > self.max_bytes:
            raise ValueError("图片为空或超过大小限制")
        try:
            with Image.open(BytesIO(data)) as image:
                suffix = FORMAT_SUFFIXES.get(image.format)
                image.verify()
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
            raise ValueError("无法读取图片内容") from exc
        if suffix is None:
            raise ValueError("仅支持 jpg/png/gif/webp/bmp 图片")
        # 内容去重让重复扫描和上传跳过文件复制和图片模型调用。
        image_id = hashlib.sha256(data).hexdigest()
        local_source = source is not None and source.is_relative_to(self.images)
        rel_path = source.relative_to(self.root).as_posix() if local_source else f"images/{image_id}{suffix}"
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            # 目录内同名文件被替换时，旧标签对应的图片内容已不存在。
            db.execute("DELETE FROM images WHERE rel_path = ? AND id != ?", (rel_path, image_id))
            existing = db.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()
            manual_tags = normalize_tags(tags)
            if existing:
                if local_source and existing["rel_path"] == rel_path:
                    manual_tags = json.loads(existing["manual_tags"])
                else:
                    manual_tags = normalize_tags(json.loads(existing["manual_tags"]) + manual_tags)
                db.execute("UPDATE images SET manual_tags = ? WHERE id = ?", (json.dumps(manual_tags), image_id))
                if not (self.root / existing["rel_path"]).is_file():
                    if local_source:
                        db.execute(
                            "UPDATE images SET rel_path = ?, filename = ? WHERE id = ?",
                            (rel_path, Path(filename).name, image_id),
                        )
                    else:
                        (self.root / existing["rel_path"]).write_bytes(data)
                return self._item(db.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()), False
            if db.execute("SELECT COUNT(*) FROM images").fetchone()[0] >= self.max_images:
                self._remove_missing(db)
                if db.execute("SELECT COUNT(*) FROM images").fetchone()[0] >= self.max_images:
                    raise ValueError("图库容量已满")
            if not local_source:
                (self.root / rel_path).write_bytes(data)
            db.execute(
                "INSERT INTO images (id, filename, rel_path, manual_tags) VALUES (?, ?, ?, ?)",
                (image_id, Path(filename).name, rel_path, json.dumps(manual_tags)),
            )
            return self._item(db.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()), True

    def import_file(self, path: Path, tags: Any = None) -> Tuple[Dict[str, Any], bool]:
        if path.stat().st_size > self.max_bytes:
            raise ValueError("图片超过大小限制")
        return self.add_bytes(path.read_bytes(), path.name, tags, source=path.resolve())

    def sync(self) -> Dict[str, Any]:
        result = {"added": 0, "existing": 0, "removed": 0, "errors": []}
        with closing(self._connect()) as db:
            previous_ids = {row["id"] for row in db.execute("SELECT id FROM images")}
        for path in sorted(self.images.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            try:
                tags = normalize_tags(path.stem) + list(path.relative_to(self.images).parts[:-1])
                _, added = self.import_file(path, tags)
                result["added" if added else "existing"] += 1
            except (ValueError, OSError) as exc:
                result["errors"].append({"file": str(path.relative_to(self.images)), "error": str(exc)})
                with closing(self._connect()) as db, db:
                    db.execute("DELETE FROM images WHERE rel_path = ?", (path.relative_to(self.root).as_posix(),))
        with closing(self._connect()) as db, db:
            self._remove_missing(db)
            current_ids = {row["id"] for row in db.execute("SELECT id FROM images")}
        result["removed"] = len(previous_ids - current_ids)
        return result

    def _remove_missing(self, db: sqlite3.Connection) -> None:
        for row in db.execute("SELECT id, rel_path FROM images").fetchall():
            if not (self.root / row["rel_path"]).is_file():
                db.execute("DELETE FROM images WHERE id = ?", (row["id"],))

    @staticmethod
    def _item(row: sqlite3.Row) -> Dict[str, Any]:
        item = dict(row)
        item["manual_tags"] = json.loads(item["manual_tags"])
        item["auto_tags"] = json.loads(item["auto_tags"])
        item["tags"] = normalize_tags(item["manual_tags"] + item["auto_tags"])
        return item

    def list_items(self) -> List[Dict[str, Any]]:
        with closing(self._connect()) as db:
            return [self._item(row) for row in db.execute("SELECT * FROM images ORDER BY rowid DESC")]

    def get(self, image_id: str) -> Dict[str, Any]:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()
        if row is None:
            raise ValueError("图片不存在")
        return self._item(row)

    def read_bytes(self, image_id: str) -> bytes:
        path = self.root / self.get(image_id)["rel_path"]
        if path.stat().st_size > self.max_bytes:
            raise ValueError("图片超过大小限制")
        return path.read_bytes()

    def set_tags(self, image_id: str, tags: Any, automatic: bool = False) -> None:
        self.get(image_id)
        column = "auto_tags" if automatic else "manual_tags"
        with closing(self._connect()) as db, db:
            db.execute(f"UPDATE images SET {column} = ? WHERE id = ?", (json.dumps(normalize_tags(tags)), image_id))
            if automatic:
                db.execute("UPDATE images SET caption_status = 'done' WHERE id = ?", (image_id,))

    def mark_caption(self, image_id: str, status: str) -> None:
        with closing(self._connect()) as db, db:
            db.execute("UPDATE images SET caption_status = ? WHERE id = ?", (status, image_id))

    def delete(self, image_id: str) -> None:
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT rel_path FROM images WHERE id = ?", (image_id,)).fetchone()
            if row is None:
                raise ValueError("图片不存在")
            (self.root / row["rel_path"]).unlink(missing_ok=True)
            db.execute("DELETE FROM images WHERE id = ?", (image_id,))

    def candidates(self, query: str, limit: int = 16, only_memes: bool = False) -> List[Dict[str, Any]]:
        query = query.lower().strip()
        terms = re.findall(r"[\w]+", query)
        ranked = []
        for item in self.list_items():
            if not (self.root / item["rel_path"]).is_file():
                continue
            if only_memes and "表情包" not in item["tags"]:
                continue
            tags = [tag.lower() for tag in item["tags"]]
            text = " ".join(tags + [item["filename"].lower()])
            score = sum(len(tag) for tag in tags if tag in query)
            score += sum(len(term) for term in terms if term in text)
            ranked.append({**item, "score": score})
        return sorted(ranked, key=lambda item: item["score"], reverse=True)[:limit]
