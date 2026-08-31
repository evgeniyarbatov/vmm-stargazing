from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from helpers import FIXTURES, write_ridge_dem
from horizon import load_dem_array
from plots import (
    altaz_to_rtheta,
    guide_label,
    guide_star,
    rel_bearing_deg,
    score_sample,
    write_plots,
)
from report import disc_stem

from gpx import read_track


class TestPlots(unittest.TestCase):
    def test_altaz_zenith_is_centre(self) -> None:
        r, _theta = altaz_to_rtheta(90.0, 123.0)
        self.assertAlmostEqual(r, 0.0)

    def test_altaz_horizon_north(self) -> None:
        r, theta = altaz_to_rtheta(0.0, 0.0)
        self.assertAlmostEqual(r, 90.0)
        self.assertAlmostEqual(theta, 0.0)

    def test_rel_bearing_ahead_left_right_wrap(self) -> None:
        self.assertAlmostEqual(rel_bearing_deg(90.0, 90.0), 0.0)
        self.assertAlmostEqual(rel_bearing_deg(100.0, 90.0), 10.0)
        self.assertAlmostEqual(rel_bearing_deg(80.0, 90.0), -10.0)
        self.assertAlmostEqual(rel_bearing_deg(350.0, 0.0), -10.0)

    def test_guide_star_prefers_brightest_in_ahead_cone(self) -> None:
        sample = {"heading_deg": 90.0}
        rows = [
            {
                "kind": "star",
                "name": "Vega",
                "alt_deg": 40.0,
                "az_deg": 100.0,
                "mag": 0.03,
                "obscured": False,
            },
            {
                "kind": "star",
                "name": "Altair",
                "alt_deg": 40.0,
                "az_deg": 95.0,
                "mag": 0.76,
                "obscured": False,
            },
            {
                "kind": "star",
                "name": "Sirius",
                "alt_deg": 40.0,
                "az_deg": 180.0,
                "mag": -1.46,
                "obscured": False,
            },
        ]
        picked = guide_star(sample, rows)
        assert picked is not None
        self.assertEqual(picked["name"], "Vega")
        self.assertEqual(guide_label(picked), "Vega 10° R")

    def test_guide_star_falls_back_to_closest_azimuth(self) -> None:
        sample = {"heading_deg": 0.0}
        rows = [
            {
                "kind": "star",
                "name": "Vega",
                "alt_deg": 40.0,
                "az_deg": 80.0,
                "mag": 0.03,
                "obscured": False,
            },
            {
                "kind": "star",
                "name": "Altair",
                "alt_deg": 40.0,
                "az_deg": 40.0,
                "mag": 0.76,
                "obscured": False,
            },
        ]
        picked = guide_star(sample, rows)
        assert picked is not None
        self.assertEqual(picked["name"], "Altair")

    def test_score_sample_rewards_open_high_dark(self) -> None:
        high = score_sample(
            {"i": 0, "night_id": 1, "lon": 0, "lat": 0, "dist_km": 1, "elev_m": 2000, "time": "t"},
            [
                {
                    "kind": "moon",
                    "name": "Moon",
                    "alt_deg": -10.0,
                    "obscured": False,
                    "illumination": 0.9,
                },
                {
                    "kind": "feature",
                    "name": "Milky Way centre",
                    "alt_deg": 30.0,
                    "obscured": False,
                },
            ],
            np.zeros(36),
            500.0,
            2000.0,
        )
        low = score_sample(
            {"i": 1, "night_id": 1, "lon": 0, "lat": 0, "dist_km": 2, "elev_m": 500, "time": "t"},
            [
                {
                    "kind": "moon",
                    "name": "Moon",
                    "alt_deg": 50.0,
                    "obscured": False,
                    "illumination": 0.9,
                },
                {
                    "kind": "feature",
                    "name": "Milky Way centre",
                    "alt_deg": -20.0,
                    "obscured": False,
                },
            ],
            np.full(36, 40.0),
            500.0,
            2000.0,
        )
        self.assertGreater(high["score"], low["score"])
        self.assertAlmostEqual(high["open_sky"], 1.0)
        self.assertGreater(low["moon_penalty"], 0.0)

    def test_disc_stem_dusk_midnight_dawn(self) -> None:
        group = [
            {"i": 0, "night_id": 1},
            {"i": 4, "night_id": 1},
            {"i": 9, "night_id": 1},
        ]
        self.assertEqual(disc_stem(group[0], group), "night1-dusk")
        self.assertEqual(disc_stem(group[1], group), "night1-midnight")
        self.assertEqual(disc_stem(group[2], group), "night1-dawn")

    def test_write_plots_creates_pngs(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        dem_path = write_ridge_dem(tmp / "dem.tif")
        array, transform, _ = load_dem_array(dem_path)
        lons, lats, eles, _ = read_track(FIXTURES / "ridge.gpx")
        nights = {
            "nights": [
                {
                    "night_id": 1,
                    "dist0_km": 0.0,
                    "dist1_km": 0.8,
                    "start": "2026-09-18T19:40:00+07:00",
                    "end": "2026-09-19T04:50:00+07:00",
                }
            ]
        }
        samples = [
            {
                "i": 0,
                "night_id": 1,
                "lon": float(lons[0]),
                "lat": float(lats[0]),
                "elev_m": 1510,
                "heading_deg": 90.0,
                "dist_km": 0.0,
                "elapsed_h": 11.7,
                "time": "2026-09-18T19:40:00+07:00",
            },
            {
                "i": 1,
                "night_id": 1,
                "lon": float(lons[-1]),
                "lat": float(lats[-1]),
                "elev_m": 1580,
                "heading_deg": 90.0,
                "dist_km": 0.6,
                "elapsed_h": 20.8,
                "time": "2026-09-19T04:50:00+07:00",
            },
        ]
        sky = []
        for sample in samples:
            sky.extend(
                [
                    {
                        "sample_i": sample["i"],
                        "kind": "planet",
                        "name": "Saturn",
                        "alt_deg": 40.0,
                        "az_deg": 120.0,
                        "mag": 0.4,
                        "obscured": False,
                    },
                    {
                        "sample_i": sample["i"],
                        "kind": "star",
                        "name": "Vega",
                        "alt_deg": 70.0,
                        "az_deg": 10.0,
                        "mag": 0.03,
                        "obscured": False,
                    },
                    {
                        "sample_i": sample["i"],
                        "kind": "star",
                        "name": "Altair",
                        "alt_deg": 45.0,
                        "az_deg": 95.0,
                        "mag": 0.76,
                        "obscured": False,
                    },
                    {
                        "sample_i": sample["i"],
                        "kind": "feature",
                        "name": "Milky Way centre",
                        "alt_deg": 25.0,
                        "az_deg": 200.0,
                        "obscured": False,
                    },
                    {
                        "sample_i": sample["i"],
                        "kind": "moon",
                        "name": "Moon",
                        "alt_deg": 20.0,
                        "az_deg": 250.0,
                        "obscured": False,
                    },
                ]
            )
        written = write_plots(
            tmp / "out", lons, lats, eles, nights, samples, sky, array, transform
        )
        stems = {p.stem for p in written}
        self.assertIn("course", stems)
        self.assertIn("profile", stems)
        self.assertIn("spots", stems)
        self.assertIn("night1-alt", stems)
        self.assertIn("night1-dusk", stems)
        self.assertIn("night1-dawn", stems)
        self.assertNotIn("steer", stems)
        self.assertNotIn("night1-steer", stems)
        for path in written:
            self.assertGreater(path.stat().st_size, 1000)
