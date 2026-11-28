"""Run: .codex-venv/bin/python -B -m unittest misc.test_html_server"""

import unittest

from src.html_server import _CatalogThreadingHTTPServer


class HtmlServerSocketTests(unittest.TestCase):
    def test_address_reuse_is_disabled(self):
        self.assertFalse(_CatalogThreadingHTTPServer.allow_reuse_address)


if __name__ == "__main__":
    unittest.main()
