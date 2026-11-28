"""アプリケーションの多重起動を防止する。"""

from pathlib import Path
import tempfile

from PySide6.QtCore import QLockFile


LOCK_FILENAME = "inf_daken_counter_obsw.lock"


class SingleInstanceLock:
    """プロセスが生存している間だけ保持される単一起動用ロック。"""

    def __init__(self, lock_path: Path | None = None):
        self.path = Path(lock_path or (Path(tempfile.gettempdir()) / LOCK_FILENAME))
        self._lock = QLockFile(str(self.path))
        # 経過時間だけではロックを破棄せず、記録されたプロセスの生存確認に任せる。
        self._lock.setStaleLockTime(0)

    def try_acquire(self) -> bool:
        return self._lock.tryLock(0)

    def release(self):
        if self._lock.isLocked():
            self._lock.unlock()
