from pathlib import Path
import unittest

from PySide6.QtCore import QUrlQuery

from src.html_catalog import HTML_VIEWS, build_obs_source_url, thumbnail_path


class HtmlCatalogTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
