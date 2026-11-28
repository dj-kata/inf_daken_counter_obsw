"""Run: .codex-venv/bin/python -B -m unittest misc.test_single_instance"""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.single_instance import SingleInstanceLock


class SingleInstanceLockTests(unittest.TestCase):
    def test_only_one_lock_can_be_acquired(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "app.lock"
            first = SingleInstanceLock(lock_path)
            second = SingleInstanceLock(lock_path)

            self.assertTrue(first.try_acquire())
            self.assertFalse(second.try_acquire())

            first.release()
            self.assertTrue(second.try_acquire())
            second.release()

    def test_windows_mutex_rejects_an_existing_instance(self):
        kernel32 = Mock()
        kernel32.CreateMutexW.return_value = 123
        lock = SingleInstanceLock()

        with patch("src.single_instance.sys.platform", "win32"), \
                patch("src.single_instance.ctypes.WinDLL", return_value=kernel32, create=True), \
                patch("src.single_instance.ctypes.get_last_error", return_value=183, create=True):
            self.assertFalse(lock.try_acquire())

        kernel32.CloseHandle.assert_called_once_with(123)

    def test_windows_mutex_is_closed_explicitly(self):
        kernel32 = Mock()
        kernel32.CreateMutexW.return_value = 456
        lock = SingleInstanceLock()

        with patch("src.single_instance.sys.platform", "win32"), \
                patch("src.single_instance.ctypes.WinDLL", return_value=kernel32, create=True), \
                patch("src.single_instance.ctypes.get_last_error", return_value=0, create=True):
            self.assertTrue(lock.try_acquire())
            lock.release()

        kernel32.CloseHandle.assert_called_once_with(456)


if __name__ == "__main__":
    unittest.main()
