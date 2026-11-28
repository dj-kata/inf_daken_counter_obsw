"""Run: .codex-venv/bin/python -B -m unittest misc.test_single_instance"""

from pathlib import Path
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
