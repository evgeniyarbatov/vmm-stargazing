from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sky import annotate_row, tag_for


class TestSky(unittest.TestCase):
    def test_tags(self) -> None:
        self.assertEqual(tag_for(70, 10), "overhead")
        self.assertEqual(tag_for(10, 90), "rising")
        self.assertEqual(tag_for(10, 270), "setting")
        self.assertEqual(tag_for(-5, 90), "down")
        self.assertEqual(tag_for(40, 200), "up")

    def test_horizon_masks_low_planet(self) -> None:
        profile = np.full(36, 15.0)
        row = annotate_row(
            {"kind": "planet", "name": "Venus", "alt_deg": 8.0, "az_deg": 270.0, "mag": -4.0},
            profile,
            buffer_deg=2.0,
            mag_limit=6.0,
        )
        assert row is not None
        self.assertTrue(row["obscured"])
        self.assertAlmostEqual(row["horizon_deg"], 15.0, delta=0.1)

    def test_faint_planet_dropped(self) -> None:
        row = annotate_row(
            {"kind": "planet", "name": "Uranus", "alt_deg": 40.0, "az_deg": 180.0, "mag": 5.7},
            None,
            buffer_deg=2.0,
            mag_limit=5.0,
        )
        self.assertIsNone(row)
