from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from report import build_markdown, fmt_hours


class TestReport(unittest.TestCase):
    def test_fmt_hours(self) -> None:
        self.assertEqual(fmt_hours(11.5), "11h 30m")

    def test_markdown_contains_night_and_planet(self) -> None:
        cfg = {"race": {"name": "VMM 100 Miles 2026"}}
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
        md = build_markdown(cfg, nights, samples, sky)
        self.assertIn("VMM 100 Miles 2026", md)
        self.assertIn("Jupiter", md)
        self.assertIn("Lyra", md)
        self.assertIn("waxing gibbous", md)
        self.assertIn("Night 1", md)
