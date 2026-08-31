from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from report import build_html, fmt_hours


class TestReport(unittest.TestCase):
    def test_fmt_hours(self) -> None:
        self.assertEqual(fmt_hours(11.5), "11h 30m")

    def test_html_contains_night_and_planet(self) -> None:
        cfg = {"race": {"name": "VMM 100 Miles 2026", "location": "Sa Pa, Lào Cai, Vietnam"}}
        nights = {
            "timezone": "Asia/Ho_Chi_Minh",
            "pace_kmh": 3.2,
            "nights": [
                {
                    "night_id": 1,
                    "start": "2026-09-18T19:40:00+07:00",
                    "end": "2026-09-19T04:50:00+07:00",
                    "duration_h": 9.166,
                    "elapsed0_h": 11.666,
                    "elapsed1_h": 20.833,
                    "dist0_km": 37.0,
                    "dist1_km": 67.0,
                }
            ],
            "events": [
                {
                    "event": "astronomical_dusk",
                    "time": "2026-09-18T19:40:00+07:00",
                    "elapsed_h": 11.666,
                }
            ],
        }
        samples = [
            {
                "i": 0,
                "night_id": 1,
                "time": "2026-09-18T23:00:00+07:00",
                "elapsed_h": 15.0,
                "dist_km": 48.0,
                "elev_m": 1700,
                "heading_deg": 90,
            }
        ]
        sky = [
            {
                "sample_i": 0,
                "kind": "planet",
                "name": "Jupiter",
                "alt_deg": 45.0,
                "az_deg": 140.0,
                "mag": -2.5,
                "obscured": False,
                "tag": "up",
            },
            {
                "sample_i": 0,
                "kind": "star",
                "name": "Vega",
                "constellation": "Lyra",
                "alt_deg": 70.0,
                "az_deg": 10.0,
                "mag": 0.03,
                "obscured": False,
                "tag": "overhead",
            },
            {
                "sample_i": 0,
                "kind": "moon",
                "name": "Moon",
                "alt_deg": 30.0,
                "az_deg": 220.0,
                "illumination": 0.7,
                "phase_name": "waxing gibbous",
                "obscured": False,
                "tag": "up",
            },
        ]
        page = build_html(cfg, nights, samples, sky)
        self.assertIn("VMM 100 Miles 2026", page)
        self.assertIn("Jupiter", page)
        self.assertIn("Lyra", page)
        self.assertIn("waxing gibbous", page)
        self.assertIn("Night 1", page)
        self.assertIn("Look up.", page)
        self.assertIn("data.json", page)
        self.assertIn('download="vmm-stargazing.json"', page)
        self.assertNotIn("steer", page)

    def test_html_embeds_plot_download_links(self) -> None:
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
        page = build_html(
            cfg,
            nights,
            samples,
            sky,
            plots={
                "course": "plots/course.png",
                "spots": "plots/spots.png",
                "night1-alt-planets": "plots/night1-alt-planets.png",
                "night1-alt-stars": "plots/night1-alt-stars.png",
                "night1-s0": "plots/night1-s0.png",
                "night1-s0-ahead": "plots/night1-s0-ahead.png",
            },
        )
        self.assertIn("plots/course.png", page)
        self.assertIn("plots/spots.png", page)
        self.assertIn("plots/night1-s0.png", page)
        self.assertIn("plots/night1-s0-ahead.png", page)
        self.assertIn("plots/night1-alt-planets.png", page)
        self.assertIn("plots/night1-alt-stars.png", page)
        self.assertIn('download="course.png"', page)
        self.assertIn('download="spots.png"', page)
        self.assertNotIn("steer", page)
        self.assertNotIn("night1-steer", page)
        self.assertNotIn("night1-alt.png", page)

    def test_html_embeds_iau_constellation_gallery(self) -> None:
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
        sky: list[dict] = []
        page = build_html(
            cfg,
            nights,
            samples,
            sky,
            iau_plots={
                1: [("Andromeda", "plots/constellations/night1/Andromeda.png")],
            },
        )
        self.assertIn("IAU constellations this night", page)
        self.assertIn("plots/constellations/night1/Andromeda.png", page)
        self.assertIn('download="Andromeda.png"', page)
