from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from helpers import FIXTURES, write_ridge_dem
from horizon import load_dem_array
from plots import altaz_to_rtheta, write_plots
from report import build_markdown, disc_stem

from gpx import read_track


class TestPlots(unittest.TestCase):
    def test_altaz_zenith_is_centre(self) -> None:
        r, _theta = altaz_to_rtheta(90.0, 123.0)
        self.assertAlmostEqual(r, 0.0)

    def test_altaz_horizon_north(self) -> None:
        r, theta = altaz_to_rtheta(0.0, 0.0)
        self.assertAlmostEqual(r, 90.0)
        self.assertAlmostEqual(theta, 0.0)

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
                        "kind": "moon",
                        "name": "Moon",
                        "alt_deg": 20.0,
                        "az_deg": 250.0,
                        "obscured": False,
                    },
                ]
            )
        written = write_plots(tmp / "out", lons, lats, eles, nights, samples, sky, array, transform)
        stems = {p.stem for p in written}
        self.assertIn("course", stems)
        self.assertIn("profile", stems)
        self.assertIn("night1-alt", stems)
        self.assertIn("night1-dusk", stems)
        self.assertIn("night1-dawn", stems)
        for path in written:
            self.assertGreater(path.stat().st_size, 1000)

    def test_markdown_embeds_plot_links(self) -> None:
        cfg = {"race": {"name": "VMM"}}
        nights = {
            "timezone": "Asia/Ho_Chi_Minh",
            "nights": [
                {
                    "night_id": 1,
                    "start": "2026-09-18T19:40:00+07:00",
                    "end": "2026-09-19T04:50:00+07:00",
                    "duration_h": 9.0,
                    "elapsed0_h": 11.7,
                    "elapsed1_h": 20.8,
                    "dist0_km": 37.0,
                    "dist1_km": 67.0,
                }
            ],
            "events": [],
        }
        samples = [
            {
                "i": 0,
                "night_id": 1,
                "time": "2026-09-18T19:40:00+07:00",
                "elapsed_h": 11.7,
                "dist_km": 37.0,
                "elev_m": 900,
                "heading_deg": 10,
            }
        ]
        sky = [
            {
                "sample_i": 0,
                "kind": "planet",
                "name": "Saturn",
                "alt_deg": 10.0,
                "az_deg": 90.0,
                "mag": 0.4,
                "obscured": False,
                "tag": "up",
            }
        ]
        md = build_markdown(
            cfg,
            nights,
            samples,
            sky,
            plots={"course": "plots/course.png", "night1-dusk": "plots/night1-dusk.png"},
        )
        self.assertIn("plots/course.png", md)
        self.assertIn("plots/night1-dusk.png", md)
