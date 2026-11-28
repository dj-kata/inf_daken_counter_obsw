from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QUrlQuery
from PySide6.QtWidgets import QApplication, QMessageBox

from src.config import Config
from src.html_catalog import (
    HTML_VIEWS,
    HtmlCatalogWindow,
    HtmlDragLabel,
    build_obs_source_url,
    thumbnail_path,
)


class HtmlCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_recommended_views_are_first(self):
        self.assertEqual(
            [view.filename for view in HTML_VIEWS[:4]],
            [
                "whole_layout.html",
                "history_cursong.html",
                "today_receipt.html",
                "today_result.html",
            ],
        )

    def test_obs_urls_have_prefixed_names_and_recommended_sizes(self):
        for view in HTML_VIEWS:
            with self.subTest(view=view.filename):
                url = build_obs_source_url(view, 8768)
                query = QUrlQuery(url)

                self.assertEqual(url.scheme(), "http")
                self.assertEqual(url.host(), "127.0.0.1")
                self.assertEqual(url.port(), 8768)
                self.assertEqual(url.path(), f"/template/{view.filename}")
                self.assertEqual(query.queryItemValue("layer-name"), view.source_name)
                self.assertEqual(query.queryItemValue("layer-width"), str(view.width))
                self.assertEqual(query.queryItemValue("layer-height"), str(view.height))

    def test_all_source_names_are_unique_and_prefixed(self):
        names = [view.source_name for view in HTML_VIEWS]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(name.startswith("infdc_") for name in names))

    def test_catalog_files_and_thumbnails_exist(self):
        template_dir = Path(__file__).resolve().parents[1] / "template"
        for view in HTML_VIEWS:
            with self.subTest(view=view.filename):
                self.assertTrue((template_dir / view.filename).is_file())
                preview_path = thumbnail_path(view, template_dir)
                if view.thumbnail_filename:
                    self.assertIsNotNone(preview_path)
                    self.assertTrue(preview_path.is_file())

    def test_template_port_defaults_and_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            config = Config(str(config_path))
            self.assertEqual(config.obs_template_port, 8768)

            config.obs_template_port = 9876
            config.save_config()
            self.assertEqual(Config(str(config_path)).obs_template_port, 9876)

    def test_applying_port_enables_all_drag_urls(self):
        requested = []
        window = HtmlCatalogWindow(
            8768,
            server_running=False,
            port_change_callback=lambda port: requested.append(port) or True,
        )
        self.addCleanup(window.deleteLater)
        labels = window.findChildren(HtmlDragLabel)
        self.assertTrue(labels)
        self.assertTrue(all(not label.isEnabled() for label in labels))

        window.port_spin.setValue(9876)
        window.apply_port()

        self.assertEqual(requested, [9876])
        self.assertTrue(all(label.isEnabled() for label in labels))
        self.assertTrue(all(label.source_url.port() == 9876 for label in labels))

    def test_rejected_port_keeps_current_server(self):
        window = HtmlCatalogWindow(
            8768,
            server_running=True,
            port_change_callback=lambda port: False,
        )
        self.addCleanup(window.deleteLater)
        window.port_spin.setValue(9876)
        with patch.object(QMessageBox, "warning") as warning:
            window.apply_port()

        self.assertEqual(window.port_spin.value(), 8768)
        self.assertEqual(window.server_port, 8768)
        self.assertTrue(all(
            label.source_url.port() == 8768
            for label in window.findChildren(HtmlDragLabel)
        ))
        warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
