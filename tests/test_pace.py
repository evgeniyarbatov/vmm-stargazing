from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from pace import load_anchor, load_scenarios, per_km_buckets, scenario_knots

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
ANCHOR = {
    "max_climb_pace": 40.0,
    "base_pace": 8.01,
    "ele_penalty": 0.0322,
    "descent_benefit": 0.0113,
    "end_fatigue": 1.538,
    "calib_distance_km": 108.6,
}


class TestPace(unittest.TestCase):
    def test_per_km_splits_gain_and_loss(self) -> None:
        dist = np.array([0.0, 500.0, 1000.0, 1500.0, 2000.0])
        elev = np.array([0.0, 50.0, 100.0, 40.0, 20.0])
        rows = per_km_buckets(dist, elev, window=1)
        self.assertEqual(rows[0][0], 0)
        self.assertGreater(rows[0][1], 0.0)
        self.assertGreater(rows[1][2], 0.0)

    def test_optimistic_faster_than_conservative(self) -> None:
        dist = np.linspace(0.0, 20_000.0, 200)
        elev = np.full(200, 1000.0)
        buckets = per_km_buckets(dist, elev, window=1)
        start = datetime(2026, 9, 18, 8, 0, tzinfo=TZ)
        sc = load_scenarios({"pace": {}})
        _, opt_h = scenario_knots(start, buckets, ANCHOR, sc["optimistic"])
        _, real_h = scenario_knots(start, buckets, ANCHOR, sc["realistic"])
        _, con_h = scenario_knots(start, buckets, ANCHOR, sc["conservative"])
        self.assertLess(opt_h, real_h)
        self.assertLess(real_h, con_h)

    def test_repo_config_has_anchor(self) -> None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        from config import load_config

        anchor = load_anchor(load_config())
        self.assertAlmostEqual(anchor["base_pace"], 8.01)
        self.assertAlmostEqual(anchor["calib_distance_km"], 108.6)
