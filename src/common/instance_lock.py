"""安装版实例租约；与更新方式无关。"""

from pathlib import Path
from typing import Any
import hashlib
import os
import sys


class FileLock:
    """进程退出即释放的跨平台文件锁；陈旧锁文件不会被误认为仍有实例。"""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = path.open("a+b")
        if self.file.tell() == 0:
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise

    def close(self) -> None:
        self.file.close()

    def __enter__(self) -> "FileLock":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()


def register_instance(root: Path) -> FileLock:
    key = hashlib.sha256(os.path.normcase(str(root.resolve())).encode("utf-8")).hexdigest()
    locks = Path(sys.prefix).resolve().parent / ".maibot-instance-locks"
    try:
        return FileLock(locks / f"{key}.lock")
    except OSError as exc:
        raise RuntimeError("这个实例正在运行，请先停止它") from exc
