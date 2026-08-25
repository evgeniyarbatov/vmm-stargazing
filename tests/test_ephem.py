from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ephem import (
    intervals_from_codes,
    moon_phase_name,
    night_windows,
    transition_events,
)

TZ = ZoneInfo("Asia/Ho_Chi_Minh")


class TestEphem(unittest.TestCase):
    def test_intervals_and_nights(self) -> None:
        t0 = datetime(2026, 9, 18, 8, 0, tzinfo=TZ)
        dusk = datetime(2026, 9, 18, 19, 40, tzinfo=TZ)
        dawn = datetime(2026, 9, 19, 4, 50, tzinfo=TZ)
        t1 = datetime(2026, 9, 19, 9, 0, tzinfo=TZ)
        trans_times = [
            datetime(2026, 9, 18, 18, 0, tzinfo=TZ),
            datetime(2026, 9, 18, 18, 25, tzinfo=TZ),
            datetime(2026, 9, 18, 18, 55, tzinfo=TZ),
            dusk,
            dawn,
            datetime(2026, 9, 19, 5, 20, tzinfo=TZ),
            datetime(2026, 9, 19, 5, 50, tzinfo=TZ),
            datetime(2026, 9, 19, 6, 15, tzinfo=TZ),
        ]
        trans_codes = [3, 2, 1, 0, 1, 2, 3, 4]
        intervals = intervals_from_codes(t0, 4, trans_times, trans_codes, t1)
        nights = night_windows(intervals)
        self.assertEqual(len(nights), 1)
        self.assertEqual(nights[0]["start"], dusk)
        self.assertEqual(nights[0]["end"], dawn)
        events = {e["event"]: e["time"] for e in transition_events(intervals)}
        self.assertEqual(events["astronomical_dusk"], dusk)
        self.assertEqual(events["astronomical_dawn"], dawn)
        self.assertEqual(events["civil_dusk"], datetime(2026, 9, 18, 18, 25, tzinfo=TZ))

    def test_moon_phase_names(self) -> None:
        self.assertEqual(moon_phase_name(0), "new")
        self.assertEqual(moon_phase_name(90), "first quarter")
        self.assertEqual(moon_phase_name(180), "full")
        self.assertEqual(moon_phase_name(270), "last quarter")
