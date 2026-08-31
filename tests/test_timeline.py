from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from timeline import (
    build_samples,
    dist_at_time,
    load_pace_knots,
    next_cutoff_after,
    pick_indices,
    time_at_dist,
)

TZ = ZoneInfo("Asia/Ho_Chi_Minh")


class TestTimeline(unittest.TestCase):
    def test_pick_indices_keeps_ends(self) -> None:
        idx = pick_indices(20, 5)
        self.assertEqual(idx[0], 0)
        self.assertEqual(idx[-1], 19)
        self.assertLessEqual(len(idx), 5)

    def test_samples_only_during_night_and_capped(self) -> None:
        lons = np.linspace(103.84, 104.00, 200)
        lats = np.full(200, 22.33)
        eles = np.full(200, 1500.0)
        start = datetime(2026, 9, 18, 8, 0, tzinfo=TZ)
        cutoff = datetime(2026, 9, 20, 9, 0, tzinfo=TZ)
        nights = [
            {
                "night_id": 1,
                "start": datetime(2026, 9, 18, 19, 40, tzinfo=TZ),
                "end": datetime(2026, 9, 19, 4, 50, tzinfo=TZ),
                "code": 0,
                "label": "night",
            }
        ]
        samples = build_samples(
            lons,
            lats,
            eles,
            None,
            None,
            start,
            cutoff,
            nights,
            sample_m=2000,
            max_per_night=6,
            fallback_elev=1500,
        )
        self.assertLessEqual(len(samples), 6)
        self.assertGreaterEqual(len(samples), 2)
        for row in samples:
            when = datetime.fromisoformat(row["time"])
            self.assertGreaterEqual(when, nights[0]["start"])
            self.assertLessEqual(when, nights[0]["end"])
            self.assertEqual(row["night_id"], 1)
        self.assertAlmostEqual(samples[0]["elapsed_h"], 11.666, delta=0.05)

    def test_cutoff_clock_wraps_to_next_day(self) -> None:
        prev = datetime(2026, 9, 18, 20, 0, tzinfo=TZ)
        nxt = next_cutoff_after(prev, "4:00")
        self.assertEqual(nxt, datetime(2026, 9, 19, 4, 0, tzinfo=TZ))

    def test_vmm_checkpoints_finish_sunday_morning(self) -> None:
        start = datetime(2026, 9, 18, 8, 0, tzinfo=TZ)
        csv_path = Path(__file__).resolve().parents[1] / "checkpoints.csv"
        knots = load_pace_knots(csv_path, start, 156_784.9)
        self.assertEqual(knots[0][1], start)
        self.assertEqual(knots[-1][1], datetime(2026, 9, 20, 9, 0, tzinfo=TZ))
        dists = [k[0] for k in knots]
        times = [k[1] for k in knots]
        self.assertEqual(dists, sorted(dists))
        self.assertEqual(times, sorted(times))
        self.assertAlmostEqual(knots[-1][0], 156_784.9, delta=1.0)

    def test_checkpoint_pace_moves_night_start_off_even_pace(self) -> None:
        start = datetime(2026, 9, 18, 8, 0, tzinfo=TZ)
        cutoff = datetime(2026, 9, 20, 9, 0, tzinfo=TZ)
        night_t = datetime(2026, 9, 18, 19, 40, tzinfo=TZ)
        knots = [
            (0.0, start),
            (40_000.0, datetime(2026, 9, 18, 20, 0, tzinfo=TZ)),
            (80_000.0, cutoff),
        ]
        even = (11.666 / 49.0) * 80.0
        d = dist_at_time(knots, night_t)
        self.assertNotAlmostEqual(d / 1000.0, even, delta=2.0)
        self.assertAlmostEqual(d / 1000.0, 38.89, delta=0.2)
        self.assertEqual(
            time_at_dist(knots, 40_000.0), datetime(2026, 9, 18, 20, 0, tzinfo=TZ)
        )
