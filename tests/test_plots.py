from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from helpers import FIXTURES, write_ridge_dem
from horizon import load_dem_array
from plots import (
    _altitude_series,
    _clock_axis,
    _frame_track,
    _local_time,
    altaz_to_rtheta,
    guide_label,
    guide_star,
    pick_best_spots,
    rel_bearing_deg,
    score_sample,
    score_samples,
    star_color,
    write_plots,
)
from report import disc_stem
from utils import bbox_of, expand_bbox

from gpx import read_track


class TestPlots(unittest.TestCase):
    def test_altaz_zenith_is_centre(self) -> None:
        r, _theta = altaz_to_rtheta(90.0, 123.0)
        self.assertAlmostEqual(r, 0.0)

    def test_altaz_horizon_north(self) -> None:
        r, theta = altaz_to_rtheta(0.0, 0.0)
        self.assertAlmostEqual(r, 90.0)
        self.assertAlmostEqual(theta, 0.0)

    def test_frame_track_crops_to_padded_course(self) -> None:
        fig, ax = plt.subplots()
        ax.set_xlim(100.0, 110.0)
        ax.set_ylim(10.0, 30.0)
        lons = np.array([103.8, 104.0])
        lats = np.array([22.3, 22.4])
        _frame_track(ax, lons, lats, pad_km=2.0)
        box = expand_bbox(bbox_of(lons, lats), 2.0)
        self.assertAlmostEqual(ax.get_xlim()[0], box["west"])
        self.assertAlmostEqual(ax.get_xlim()[1], box["east"])
        self.assertAlmostEqual(ax.get_ylim()[0], box["south"])
        self.assertAlmostEqual(ax.get_ylim()[1], box["north"])
        plt.close(fig)

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

    def test_score_sample_rewards_open_ahead(self) -> None:
        sample = {
            "i": 0,
            "night_id": 1,
            "lon": 0,
            "lat": 0,
            "dist_km": 1,
            "elev_m": 1000,
            "heading_deg": 90.0,
            "time": "t",
        }
        wall_ahead = np.concatenate([np.full(19, 40.0), np.zeros(17)])
        open_ahead = np.concatenate([np.zeros(19), np.full(17, 40.0)])
        closed = score_sample(sample, [], wall_ahead, 500.0, 1500.0)
        opened = score_sample(sample, [], open_ahead, 500.0, 1500.0)
        self.assertGreater(opened["open_ahead"], closed["open_ahead"])
        self.assertGreater(opened["score"], closed["score"])

    def test_score_samples_elev_is_per_night(self) -> None:
        samples = [
            {"i": 0, "night_id": 1, "lon": 0, "lat": 0, "dist_km": 10, "elev_m": 700, "time": "t"},
            {"i": 1, "night_id": 1, "lon": 0, "lat": 0, "dist_km": 20, "elev_m": 1000, "time": "t"},
            {"i": 2, "night_id": 2, "lon": 0, "lat": 0, "dist_km": 150, "elev_m": 1000, "time": "t"},
            {"i": 3, "night_id": 2, "lon": 0, "lat": 0, "dist_km": 155, "elev_m": 2000, "time": "t"},
        ]
        scored = {int(row["i"]): row for row in score_samples(samples, [], {})}
        self.assertAlmostEqual(scored[1]["elev_score"], 1.0)
        self.assertAlmostEqual(scored[2]["elev_score"], 0.0)

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
        self.assertIn("night1-alt-planet-saturn", stems)
        self.assertIn("night1-alt-moon-moon", stems)
        self.assertIn("night1-alt-star-vega", stems)
        self.assertIn("night1-alt-star-altair", stems)
        self.assertNotIn("night1-alt-planets", stems)
        self.assertNotIn("night1-alt-stars", stems)
        self.assertTrue({"night1-s0", "night1-s1"} & stems)
        self.assertTrue({"night1-s0-ahead", "night1-s1-ahead"} & stems)
        self.assertTrue({"night1-s0-course", "night1-s1-course"} & stems)
        self.assertNotIn("night1-dusk", stems)
        self.assertNotIn("night1-spot-ahead", stems)
        self.assertNotIn("night1-alt", stems)
        self.assertNotIn("steer", stems)
        self.assertNotIn("night1-steer", stems)
        gpx_path = tmp / "out" / "stargazing-spots.gpx"
        self.assertTrue(gpx_path.is_file())
        self.assertIn("<wpt", gpx_path.read_text(encoding="utf-8"))
        for path in written:
            self.assertGreater(path.stat().st_size, 1000)

    def test_pick_best_spots_keeps_gap(self) -> None:
        scores = [
            {"i": 0, "night_id": 1, "dist_km": 10.0, "score": 0.9, "lon": 0, "lat": 0},
            {"i": 1, "night_id": 1, "dist_km": 12.0, "score": 0.8, "lon": 0, "lat": 0},
            {"i": 2, "night_id": 1, "dist_km": 40.0, "score": 0.7, "lon": 0, "lat": 0},
        ]
        picked = pick_best_spots(scores, min_gap_km=6.0, max_per_night=4)
        ids = [int(s["i"]) for s in picked]
        self.assertEqual(ids, [0, 2])

    def test_pick_best_spots_keeps_stretch_peak(self) -> None:
        scores = [
            {"i": 0, "night_id": 1, "dist_km": 10.0, "score": 0.90, "lon": 0, "lat": 0},
            {"i": 1, "night_id": 1, "dist_km": 16.0, "score": 0.65, "lon": 0, "lat": 0},
            {"i": 2, "night_id": 1, "dist_km": 32.0, "score": 0.72, "lon": 0, "lat": 0},
            {"i": 3, "night_id": 1, "dist_km": 38.0, "score": 0.71, "lon": 0, "lat": 0},
            {"i": 4, "night_id": 1, "dist_km": 44.0, "score": 0.70, "lon": 0, "lat": 0},
        ]
        picked = pick_best_spots(scores, min_gap_km=5.0, max_per_night=8, score_floor=0.7)
        ids = [int(s["i"]) for s in picked]
        self.assertIn(0, ids)
        self.assertIn(1, ids)
        self.assertIn(2, ids)

    def test_pick_best_spots_skips_below_floor(self) -> None:
        scores = [
            {"i": 0, "night_id": 1, "dist_km": 10.0, "score": 0.90, "lon": 0, "lat": 0},
            {"i": 1, "night_id": 1, "dist_km": 16.0, "score": 0.40, "lon": 0, "lat": 0},
            {"i": 2, "night_id": 1, "dist_km": 40.0, "score": 0.80, "lon": 0, "lat": 0},
        ]
        picked = pick_best_spots(scores, min_gap_km=5.0, max_per_night=8, score_floor=0.7)
        ids = [int(s["i"]) for s in picked]
        self.assertEqual(ids, [0, 2])

    def test_pick_best_spots_keeps_short_night_end(self) -> None:
        scores = [
            {"i": 0, "night_id": 2, "dist_km": 152.0, "score": 0.88, "lon": 0, "lat": 0},
            {"i": 1, "night_id": 2, "dist_km": 156.8, "score": 0.65, "lon": 0, "lat": 0},
        ]
        picked = pick_best_spots(scores, min_gap_km=4.0, max_per_night=8, score_floor=0.7)
        self.assertEqual([int(s["i"]) for s in picked], [0, 1])

    def test_star_colors_differ(self) -> None:
        self.assertNotEqual(star_color("Vega"), star_color("Altair"))
        self.assertEqual(star_color("Vega"), star_color("Vega"))

    def test_local_time_drops_offset(self) -> None:
        self.assertEqual(
            _local_time("2026-09-18T19:40:00+07:00"),
            datetime(2026, 9, 18, 19, 40),
        )

    def test_clock_axis_hhmm_ticks(self) -> None:
        fig, ax = plt.subplots()
        span = [datetime(2026, 9, 18, 19, 40), datetime(2026, 9, 19, 4, 50)]
        ax.plot(span, [10.0, 40.0])
        _clock_axis(ax, span)
        fig.canvas.draw()
        labels = [t.get_text() for t in ax.get_xticklabels() if t.get_text()]
        xlabel = ax.get_xlabel()
        plt.close(fig)
        self.assertTrue(labels)
        self.assertTrue(all(len(t) == 5 and t[2] == ":" for t in labels))
        self.assertIn("20:00", labels)
        self.assertNotEqual(xlabel, "elapsed h")

    def test_altitude_series_one_body_each(self) -> None:
        samples = [
            {"i": 0, "elapsed_h": 12.0, "time": "2026-09-18T20:00:00+07:00"},
            {"i": 1, "elapsed_h": 18.0, "time": "2026-09-19T02:00:00+07:00"},
        ]
        sky = [
            {
                "sample_i": 0,
                "kind": "planet",
                "name": "Saturn",
                "alt_deg": 20.0,
                "obscured": False,
            },
            {
                "sample_i": 1,
                "kind": "planet",
                "name": "Saturn",
                "alt_deg": 40.0,
                "obscured": False,
            },
            {
                "sample_i": 0,
                "kind": "moon",
                "name": "Moon",
                "alt_deg": 10.0,
                "obscured": False,
            },
            {
                "sample_i": 1,
                "kind": "moon",
                "name": "Moon",
                "alt_deg": -5.0,
                "obscured": False,
            },
            {
                "sample_i": 0,
                "kind": "planet",
                "name": "Venus",
                "alt_deg": -20.0,
                "obscured": False,
            },
            {
                "sample_i": 1,
                "kind": "planet",
                "name": "Venus",
                "alt_deg": -10.0,
                "obscured": False,
            },
            {
                "sample_i": 0,
                "kind": "star",
                "name": "Vega",
                "alt_deg": 70.0,
                "obscured": False,
            },
            {
                "sample_i": 1,
                "kind": "star",
                "name": "Altair",
                "alt_deg": 45.0,
                "obscured": False,
            },
        ]
        planets = _altitude_series(samples, sky, "planets")
        self.assertEqual([name for _kind, name, *_rest in planets], ["Saturn", "Moon"])
        self.assertEqual(planets[0][2], [datetime(2026, 9, 18, 20, 0), datetime(2026, 9, 19, 2, 0)])
        stars = _altitude_series(samples, sky, "stars")
        self.assertEqual([name for _kind, name, *_rest in stars], ["Altair", "Vega"])
