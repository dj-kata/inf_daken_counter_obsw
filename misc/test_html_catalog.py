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

    def test_obs_url_has_prefixed_name_and_size(self):
        view = HTML_VIEWS[0]
        url = build_obs_source_url(view, Path("template"))
        query = QUrlQuery(url)

        self.assertTrue(url.isLocalFile())
        self.assertEqual(Path(url.toLocalFile()).name, "whole_layout.html")
        self.assertEqual(Path(url.toLocalFile()).parent.name, "template")
        self.assertEqual(query.queryItemValue("layer-name"), "infdc_whole_layout")
        self.assertEqual(query.queryItemValue("layer-width"), "1920")
        self.assertEqual(query.queryItemValue("layer-height"), "1080")

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
