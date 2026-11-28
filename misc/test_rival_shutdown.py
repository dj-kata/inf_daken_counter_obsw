"""Run: .codex-venv/bin/python -B -m unittest misc.test_rival_shutdown"""

import unittest
from unittest.mock import Mock

from src.rival_data import RivalManager


class RivalShutdownTests(unittest.TestCase):
    def test_shutdown_waits_for_running_worker(self):
        manager = RivalManager()
        manager._worker = worker = Mock()
        worker.isRunning.return_value = True

        self.assertFalse(manager.shutdown())

        worker.request_cancel.assert_called_once_with()
        self.assertIs(manager._worker, worker)

    def test_shutdown_releases_stopped_worker(self):
        manager = RivalManager()
        manager._worker = worker = Mock()
        worker.isRunning.return_value = False

        self.assertTrue(manager.shutdown())

        worker.request_cancel.assert_called_once_with()
        worker.deleteLater.assert_called_once_with()
        self.assertIsNone(manager._worker)


if __name__ == "__main__":
    unittest.main()
