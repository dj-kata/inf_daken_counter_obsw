"""Run: .codex-venv/bin/python -B -m unittest misc.test_result_stats_writer"""

import unittest

from PIL import Image, ImageDraw

from src.classes import average_release
from src.result_stats_writer import ResultStatsWriter


class ResultStatsWriterReleaseGraphTests(unittest.TestCase):
    def setUp(self):
        self.writer = ResultStatsWriter()
        self.release = average_release(
            [55.0, 61.0, None, 78.0],
            interval_seconds=10.0,
            key_counts_cumulative=[0, 10, 25, 25, 40],
            other_counts_cumulative=[0, 2, 5, 6, 10],
            release_sample_counts=[9, 14, 0, 13],
        )

    def test_converts_cumulative_counts_to_interval_counts(self):
        data = self.writer._release_graph_data(self.release)

        self.assertEqual(data["values"], [55.0, 61.0, None, 78.0])
        self.assertEqual(data["key_counts"], [10, 15, 0, 15])
        self.assertEqual(data["other_counts"], [2, 3, 1, 4])
        self.assertEqual(data["average"], 194 / 3)

    def test_axis_labels_are_multiples_of_ten_only(self):
        _, _, ticks = self.writer._release_axis_range_and_ticks(
            [55.0, 61.0, 78.0], 194 / 3
        )

        self.assertEqual(ticks, [60, 70, 80])
        self.assertTrue(all(tick % 10 == 0 for tick in ticks))

    def test_draws_release_average_and_stacked_bar_colors(self):
        image = Image.new("RGBA", (790, 190), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        self.writer._draw_release_graph(
            draw,
            0,
            0,
            790,
            190,
            self.writer._release_graph_data(self.release),
        )

        colors = set(image.get_flattened_data())
        self.assertIn((65, 225, 255, 255), colors)
        self.assertIn((255, 220, 75, 255), colors)
        self.assertIn((55, 145, 255, 230), colors)
        self.assertIn((255, 105, 75, 230), colors)


if __name__ == "__main__":
    unittest.main()
