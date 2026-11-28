"""アプリケーションの多重起動を防止する。"""

import ctypes
from pathlib import Path
import sys
import tempfile

LOCK_FILENAME = "inf_daken_counter_obsw.lock"
MUTEX_NAME = r"Local\dj-kata.inf_daken_counter_obsw"
ERROR_ALREADY_EXISTS = 183


class SingleInstanceLock:
    """プロセスが生存している間だけ保持される単一起動用ロック。"""

    def __init__(self, lock_path: Path | None = None):
        self.path = Path(lock_path or (Path(tempfile.gettempdir()) / LOCK_FILENAME))
        self._handle = None
        self._lock = None

    def try_acquire(self) -> bool:
        if self._handle is not None or (
            self._lock is not None and self._lock.isLocked()
        ):
            return True
        if sys.platform == "win32":
            return self._try_acquire_windows_mutex()

        # Windows以外では開発・テスト用にQtのロックファイルを使う。
        from PySide6.QtCore import QLockFile

        self._lock = QLockFile(str(self.path))
        self._lock.setStaleLockTime(0)
        return self._lock.tryLock(0)

    def _try_acquire_windows_mutex(self) -> bool:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_bool

        handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        self._handle = handle
        return True

    def release(self):
        if self._handle is not None:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel32.CloseHandle.restype = ctypes.c_bool
            kernel32.CloseHandle(self._handle)
            self._handle = None
        if self._lock is not None and self._lock.isLocked():
            self._lock.unlock()
