"""Run: python -B -m unittest misc.test_import_release_notes"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from io import BytesIO

from misc.import_release_notes import fetch_releases, nest_headings, render_releases, select_releases


def release(tag, date="2026-09-01T12:00:00Z", **kwargs):
    return dict(tag_name=tag, name=tag, published_at=date, draft=False, prerelease=False,
                html_url=f"https://github.com/dj-kata/inf_daken_counter_obsw/releases/tag/{tag}",
                body="# 更新内容\n- 修正しました", **kwargs)


class ImportReleaseNotesTests(unittest.TestCase):
    def test_select_recent_published_stable_releases_by_date(self):
        older = release("old")
        recent = release("recent", "2026-10-01T12:00:00Z")
        preview = release("preview")
        preview["prerelease"] = True
        draft = release("draft")
        draft["draft"] = True
        self.assertEqual(select_releases([older, draft, preview, recent], limit=1), [recent])
        self.assertEqual(len(select_releases([older, preview], include_prereleases=True)), 2)

    def test_explicit_tags_include_requested_preview_but_never_drafts(self):
        preview = release("preview")
        preview["prerelease"] = True
        self.assertEqual(select_releases([preview, release("stable")], tags=["preview"]), [preview])
        with self.assertRaisesRegex(ValueError, "missing"):
            select_releases([preview], tags=["missing"])
        preview["draft"] = True
        with self.assertRaises(ValueError):
            select_releases([preview], tags=["preview"])

    def test_nested_headings_preserve_code_and_links(self):
        body = "# 更新\r\n## 詳細\r\n```md\r\n# code\r\n```\r\n~~~\r\n## code2\r\n~~~\r\n[画像](https://example.com/image.png)"
        self.assertEqual(nest_headings(body),
                         "### 更新\n#### 詳細\n```md\n# code\n```\n~~~\n## code2\n~~~\n[画像](https://example.com/image.png)")
        rendered = render_releases([release("v1")])
        self.assertIn("## v1\n", rendered)
        self.assertIn("### 更新内容", rendered)
        self.assertIn("公開日（UTC）: 2026-09-01", rendered)
        self.assertIn("releases/tag/v1", rendered)

    def test_fetch_follows_pagination(self):
        first = [release(str(index)) for index in range(100)]
        second = [release("last")]
        with patch("misc.import_release_notes.urlopen", side_effect=[
            BytesIO(json.dumps(first).encode()), BytesIO(json.dumps(second).encode()),
        ]) as opened:
            self.assertEqual(len(fetch_releases()), 101)
            self.assertTrue(opened.call_args_list[1].args[0].full_url.endswith("page=2"))

    def test_imported_manual_links_stay_within_site(self):
        root = "https://github.com/dj-kata/inf_daken_counter_obsw/wiki"
        body = (f"[wiki]({root}/%E5%90%84%E3%83%93%E3%83%A5%E3%83%BC%E3%81%AEHTML%E3%81%AB%E3%81%A4%E3%81%84%E3%81%A6#old)\n"
                f"[OBS]({root}/OBS-WebSocket%E8%A8%AD%E5%AE%9A)\n"
                f"[説明書]({root})\n"
                f"[スマホ]({root}/スマホ用ビューの利用方法)")
        converted = nest_headings(body)
        self.assertNotIn("/wiki", converted)
        self.assertIn("[使い方](obs-views.md)", converted)
        self.assertIn("[OBS](obs-control.md)", converted)
        self.assertIn("[説明書](index.md)", converted)
        self.assertIn("[スマホ](mobile.md)", converted)

    def test_cli_offline_import_and_failure_preserve_existing_output(self):
        script = Path(__file__).with_name("import_release_notes.py")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "releases.json"
            output = root / "releases.md"
            data.write_text(json.dumps([release("v1")]), encoding="utf-8")
            command = [sys.executable, "-B", str(script), "--input-json", str(data), "--output", str(output)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            original = output.read_bytes()
            result = subprocess.run(command + ["--tag", "missing"], capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), original)
            data.write_text("invalid JSON", encoding="utf-8")
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
