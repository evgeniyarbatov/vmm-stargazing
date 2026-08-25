from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from catalog import NAV_STARS, STARS


class TestCatalog(unittest.TestCase):
    def test_unique_star_names(self) -> None:
        names = [s.name for s in STARS]
        self.assertEqual(len(names), len(set(names)))

    def test_ra_dec_ranges(self) -> None:
        for star in STARS:
            self.assertGreaterEqual(star.ra_hours, 0)
            self.assertLess(star.ra_hours, 24)
            self.assertGreaterEqual(star.dec_deg, -90)
            self.assertLessEqual(star.dec_deg, 90)

    def test_nav_stars_present(self) -> None:
        names = {s.name for s in STARS}
        self.assertTrue(names >= NAV_STARS)
