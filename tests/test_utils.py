from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from utils import (
    bearing_deg,
    densify_lonlat,
    destination_lonlat,
    expand_bbox,
    haversine_m,
    lerp_wrap_deg,
    sample_along,
)


class TestUtils(unittest.TestCase):
    def test_haversine_known_short_segment(self) -> None:
        d = haversine_m(103.84, 22.33, 103.85, 22.33)
        self.assertGreater(d, 900)
        self.assertLess(d, 1200)

    def test_bearing_east_is_90(self) -> None:
        self.assertAlmostEqual(bearing_deg(103.84, 22.33, 103.85, 22.33), 90.0, delta=1.0)

    def test_bearing_north_is_0(self) -> None:
        self.assertAlmostEqual(bearing_deg(103.84, 22.33, 103.84, 22.34), 0.0, delta=1.0)

    def test_densify_increases_points(self) -> None:
        lons = np.array([103.84, 103.85])
        lats = np.array([22.33, 22.33])
        dlon, dlat = densify_lonlat(lons, lats, spacing_m=50)
        self.assertGreater(len(dlon), 10)
        self.assertEqual(len(dlon), len(dlat))
        self.assertAlmostEqual(float(dlon[0]), 103.84)
        self.assertAlmostEqual(float(dlon[-1]), 103.85)

    def test_sample_along_includes_start_and_end(self) -> None:
        lons = np.linspace(103.84, 103.85, 50)
        lats = np.full(50, 22.33)
        slon, slat, dist, _ele = sample_along(lons, lats, sample_m=200)
        self.assertEqual(float(dist[0]), 0.0)
        self.assertGreaterEqual(len(dist), 5)
        self.assertEqual(len(slon), len(slat))

    def test_expand_bbox_pads_both_axes(self) -> None:
        box = {"west": 103.8, "south": 22.3, "east": 104.0, "north": 22.4}
        padded = expand_bbox(box, buffer_km=5)
        self.assertLess(padded["west"], box["west"])
        self.assertGreater(padded["east"], box["east"])

    def test_destination_east_increases_lon(self) -> None:
        lon, lat = destination_lonlat(103.84, 22.33, 90.0, 1000.0)
        self.assertGreater(lon, 103.84)
        self.assertAlmostEqual(lat, 22.33, delta=0.002)

    def test_lerp_wrap_closes_the_circle(self) -> None:
        profile = np.array([10.0, 0.0, 0.0, 20.0])
        self.assertAlmostEqual(lerp_wrap_deg(profile, 0.0), 10.0)
        self.assertGreater(lerp_wrap_deg(profile, 350.0), 10.0)
