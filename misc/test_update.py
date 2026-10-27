"""Run: .codex-venv/bin/python -B -m unittest misc.test_update

Load the updater class without the unused HTTP/HTML/GUI dependencies so the
handoff can be tested on Linux. Windows batch execution needs a Windows test.
"""

import ast
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile


SOURCE = Path(__file__).resolve().parents[1] / 'src/update.py'
tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
updater_class = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                     and node.name == 'GitHubUpdater')
namespace = dict(os=os, sys=sys, Path=Path, shutil=shutil, subprocess=subprocess,
                 logger=Mock(), traceback=SimpleNamespace(format_exc=Mock()),
                 messagebox=Mock(), threading=Mock())
exec(compile(ast.Module(body=[updater_class], type_ignores=[]), str(SOURCE), 'exec'), namespace)
GitHubUpdater = namespace['GitHubUpdater']


class UpdateTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name) / '日本語 & space! (100%)'
        self.base.mkdir()
        self.updater = GitHubUpdater(zipfile_basename='inf_daken_counter',
                                     main_exe_name='notes_counter.exe')
        self.updater.base_dir = self.base
        self.updater.temp_dir = self.base / 'tmp'
        self.source = self.updater.temp_dir / 'inf_daken_counter'
        (self.source / 'lib').mkdir(parents=True)
        for name in ('notes_counter.exe', 'version.txt', 'lib/Qt6Core.dll'):
            (self.source / name).write_bytes(b'new')
            target = self.base / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'old')
        self.updater.root = Mock()

    def script(self):
        with patch.object(sys, 'platform', 'win32'):
            path = self.updater.create_restart_script()
        raw = path.read_bytes()
        self.assertIn(b'\r\n', raw)
        return raw.decode('utf-8').replace('\r\n', '\n')

    def test_preparation_leaves_installed_files_untouched(self):
        self.script()
        for name in ('notes_counter.exe', 'version.txt', 'lib/Qt6Core.dll'):
            self.assertEqual((self.base / name).read_bytes(), b'old')

    def test_batch_waits_for_only_the_updating_process_before_copying(self):
        script = self.script()
        self.assertIn(f'tasklist /FI "PID eq {os.getpid()}"', script)
        self.assertLess(script.index(':wait_exit'), script.index('robocopy '))
        self.assertIn('GEQ 60 goto wait_failed', script)
        self.assertNotIn('taskkill', script)

    def test_copy_errors_stop_before_version_update_and_restart(self):
        script = self.script()
        copy = script.index('robocopy ')
        failure = script.index('if errorlevel 8 goto failed')
        version = script.index('copy /Y ')
        restart = script.index('start "" ')
        self.assertLess(copy, failure)
        self.assertLess(failure, version)
        self.assertLess(version, restart)
        self.assertIn('/XF version.txt', script)
        self.assertIn('/IS /IT /R:5 /W:2', script)
        self.assertIn('if errorlevel 1 goto failed', script[version:restart])
        self.assertNotIn('start ', script[script.index(':failed'):])
        self.assertNotIn('rmdir', script)
        self.assertIn('update_install.log', script)

    def test_batch_preserves_unicode_spaces_and_shell_characters_in_paths(self):
        script = self.script()
        self.assertIn('setlocal DisableDelayedExpansion', script)
        self.assertIn('日本語 & space! (100%%)', script)
        self.assertIn(f'set "UPDATE_DEST={str(self.base).replace("%", "%%")}"', script)
        self.assertIn('"%UPDATE_SOURCE%" "%UPDATE_DEST%"', script)

    def test_missing_payload_is_rejected_before_handoff(self):
        for name in ('notes_counter.exe', 'version.txt', 'lib'):
            path = self.source / name
            moved = path.with_name(path.name + '.hidden')
            path.rename(moved)
            try:
                with patch.object(sys, 'platform', 'win32'), self.assertRaisesRegex(
                        RuntimeError, '必要なファイル'):
                    self.updater.create_restart_script()
                self.assertFalse((self.base / 'restart_update.bat').exists())
            finally:
                moved.rename(path)

    def test_non_windows_update_fails_without_changing_installation(self):
        with patch.object(sys, 'platform', 'linux'), self.assertRaisesRegex(
                RuntimeError, 'Windows'):
            self.updater.create_restart_script()
        self.assertEqual((self.base / 'notes_counter.exe').read_bytes(), b'old')

    def test_extraction_uses_base_directory_even_with_different_cwd(self):
        archive = self.base / 'update.zip'
        with ZipFile(archive, 'w') as zipfile:
            zipfile.writestr('inf_daken_counter/new.dll', b'dll')
        self.updater.extract_zip_file(archive)
        self.assertEqual((self.source / 'new.dll').read_bytes(), b'dll')

    def test_restart_launches_external_process_and_requests_main_thread_exit(self):
        self.script()
        with patch.object(subprocess, 'Popen') as launch, patch.object(
                subprocess, 'CREATE_NEW_CONSOLE', 16, create=True):
            self.updater.restart_program()
        self.assertTrue(self.updater.update_pending)
        self.updater.root.after.assert_called_once_with(0, self.updater.root.destroy)
        self.assertEqual(launch.call_args.args[0],
                         ['cmd.exe', '/d', '/c', str(self.base / 'restart_update.bat')])
        self.assertEqual(launch.call_args.kwargs['cwd'], self.base)
        self.assertNotIn('shell', launch.call_args.kwargs)

    def test_failed_launch_does_not_request_exit(self):
        self.script()
        with patch.object(subprocess, 'Popen', side_effect=OSError('launch failed')), \
                patch.object(subprocess, 'CREATE_NEW_CONSOLE', 16, create=True), \
                self.assertRaises(OSError):
            self.updater.restart_program()
        self.assertFalse(self.updater.update_pending)
        self.updater.root.after.assert_not_called()

    def test_update_flow_hands_off_without_copying_or_renaming_running_files(self):
        self.updater.check_for_updates = Mock(return_value=(True, '3.1.3', 'url'))
        self.updater.create_gui = Mock()
        self.updater.cleanup = Mock()
        self.updater.download_file = Mock()
        self.updater.extract_zip_file = Mock()
        self.updater.update_status = Mock()
        namespace['messagebox'].askyesno.return_value = True
        # Run the download worker synchronously; GUI callbacks stay queued.
        namespace['threading'].Thread.side_effect = lambda target, **kw: SimpleNamespace(start=target)
        with patch.object(sys, 'platform', 'win32'), \
                patch.object(subprocess, 'CREATE_NEW_CONSOLE', 16, create=True), \
                patch.object(subprocess, 'Popen'), \
                patch.object(os, 'rename', side_effect=AssertionError('running exe renamed')), \
                patch.object(shutil, 'copy2', side_effect=AssertionError('running DLL copied')):
            self.assertTrue(self.updater.check_and_update())
        self.assertEqual((self.base / 'lib/Qt6Core.dll').read_bytes(), b'old')

    def test_failed_handoff_is_not_reported_as_an_update(self):
        self.updater.check_for_updates = Mock(return_value=(True, '3.1.3', 'url'))
        for name in ('create_gui', 'cleanup', 'download_file', 'extract_zip_file', 'update_status'):
            setattr(self.updater, name, Mock())
        namespace['messagebox'].askyesno.return_value = True
        namespace['threading'].Thread.side_effect = lambda target, **kw: SimpleNamespace(start=target)
        with patch.object(sys, 'platform', 'win32'), \
                patch.object(subprocess, 'CREATE_NEW_CONSOLE', 16, create=True), \
                patch.object(subprocess, 'Popen', side_effect=OSError('launch failed')):
            self.assertFalse(self.updater.check_and_update())
        self.assertEqual((self.base / 'version.txt').read_bytes(), b'old')

    def test_entry_point_exits_in_main_thread_after_handoff(self):
        entry = SOURCE.parents[1] / 'notes_counter.pyw'
        tree = ast.parse(entry.read_text(encoding='utf-8'))
        guard = next(node for node in ast.walk(tree) if isinstance(node, ast.If)
                     and isinstance(node.test, ast.Call)
                     and isinstance(node.test.func, ast.Attribute)
                     and node.test.func.attr == 'check_and_update')
        updater = Mock()
        with self.assertRaises(SystemExit):
            exec(compile(ast.Module(body=[guard], type_ignores=[]), str(entry), 'exec'),
                 dict(updater=updater, sys=sys))


if __name__ == '__main__':
    unittest.main()
