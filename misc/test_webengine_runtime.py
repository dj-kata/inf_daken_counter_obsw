"""Run: .codex-venv/bin/python -B -m unittest misc.test_webengine_runtime"""

import ast
import configparser
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.webengine_runtime import configure_frozen_webengine, validate_webengine_version


class WebEngineRuntimeTests(unittest.TestCase):
    def test_qt_versions_with_the_native_gpu_crash_are_rejected(self):
        for version in ('6.9.3', '6.10.0', '6.10.1', b'6.10.1'):
            with self.subTest(version=version), self.assertRaisesRegex(RuntimeError, '6.10.2'):
                validate_webengine_version(version)
        for version in ('6.10.2', '6.10.3', '6.11.0', b'6.10.2'):
            validate_webengine_version(version)

    def test_old_qt_is_rejected_before_a_webengine_window_is_created(self):
        from src.game_overlay import HtmlLogOverlay
        version = Mock()
        version.toString.return_value = '6.10.1'
        with patch('src.game_overlay.QLibraryInfo.version', return_value=version), \
                patch('src.game_overlay.sys.frozen', False, create=True), \
                patch('src.game_overlay.install_qt_diagnostics'), \
                patch('src.game_overlay.OverlayWindow.__init__') as create_window:
            with self.assertRaisesRegex(RuntimeError, 'QTBUG-142497'):
                HtmlLogOverlay(Path('template'))
            create_window.assert_not_called()

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.bundle = Path(directory.name) / 'application with spaces'
        self.qt = self.bundle / 'lib' / 'PySide6'
        self.files = [self.qt / 'QtWebEngineProcess.exe',
                      self.qt / 'translations/qtwebengine_locales/en-US.pak'] + [
            self.qt / 'resources' / name for name in (
                'icudtl.dat', 'qtwebengine_resources.pak',
                'qtwebengine_resources_100p.pak', 'qtwebengine_resources_200p.pak',
                'v8_context_snapshot.bin')]
        for path in self.files:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'test runtime')

    def test_paths_override_foreign_qt_installation_and_do_not_depend_on_cwd(self):
        with patch.dict(os.environ, {'QTWEBENGINEPROCESS_PATH': 'wrong/QtWebEngineProcess.exe'}):
            paths = configure_frozen_webengine(self.bundle)
            self.assertEqual(Path(paths['QTWEBENGINEPROCESS_PATH']), self.qt / 'QtWebEngineProcess.exe')
            self.assertEqual(Path(paths['QTWEBENGINE_RESOURCES_PATH']), self.qt / 'resources')
            self.assertEqual(Path(paths['QTWEBENGINE_LOCALES_PATH']), self.qt / 'translations/qtwebengine_locales')
            for key, value in paths.items():
                self.assertTrue(Path(value).is_absolute())
                self.assertEqual(os.environ[key], value)

    def test_packaged_qt_conf_points_at_the_bundled_runtime(self):
        # Read the build configuration without importing setup.py or building.
        source = Path(__file__).resolve().parents[1] / 'setup.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        assignment = next(node for node in ast.walk(tree)
                          if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == 'qt_conf_content'
                                  for target in node.targets))
        config = configparser.ConfigParser()
        config.read_string(ast.literal_eval(assignment.value))
        paths = config['Paths']
        prefix = self.bundle / paths['Prefix']
        self.assertTrue((prefix / paths['LibraryExecutables'] / 'QtWebEngineProcess.exe').is_file())
        self.assertTrue((prefix / paths['Data'] / 'resources/icudtl.dat').is_file())
        self.assertTrue((prefix / paths['Translations'] / 'qtwebengine_locales/en-US.pak').is_file())

    def test_each_missing_runtime_file_is_a_python_error_without_changing_environment(self):
        for path in self.files:
            with self.subTest(path=path.name):
                path.unlink()
                before = dict(os.environ)
                with self.assertRaises(FileNotFoundError) as error:
                    configure_frozen_webengine(self.bundle)
                self.assertIn(str(path), str(error.exception))
                self.assertEqual(dict(os.environ), before)
                path.write_bytes(b'test runtime')

    def test_overlay_checks_bundle_before_constructing_any_window(self):
        from src.game_overlay import HtmlLogOverlay
        missing = self.files[0]
        missing.unlink()
        with patch('src.game_overlay.sys.frozen', True, create=True), \
                patch('src.game_overlay.sys.platform', 'win32'), \
                patch('src.game_overlay.sys.executable', str(self.bundle / 'notes_counter.exe')), \
                patch('src.game_overlay.install_qt_diagnostics'), \
                patch('src.game_overlay.OverlayWindow.__init__') as create_window:
            with self.assertRaises(FileNotFoundError):
                HtmlLogOverlay(self.bundle / 'template')
            create_window.assert_not_called()

    def test_qt_fatal_message_is_logged_and_previous_handler_preserved(self):
        from PySide6.QtCore import QtMsgType
        from src.game_overlay import install_qt_diagnostics
        previous = Mock()
        with patch('src.game_overlay._qt_message_handler', None), \
                patch('src.game_overlay.qInstallMessageHandler', return_value=previous) as install, \
                patch('src.game_overlay.logger') as logger:
            install_qt_diagnostics()
            install_qt_diagnostics()
            install.assert_called_once()
            handler = install.call_args.args[0]
            handler(QtMsgType.QtFatalMsg, None, 'Could not find QtWebEngineProcess.exe')
            logger.critical.assert_called_once_with('Qt fatal: %s', 'Could not find QtWebEngineProcess.exe')
            previous.assert_called_once()


if __name__ == '__main__':
    unittest.main()
