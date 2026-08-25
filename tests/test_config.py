from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from config import load_config, race_window


class TestConfig(unittest.TestCase):
    def test_repo_config_window(self) -> None:
        cfg = load_config()
        start, cutoff = race_window(cfg)
        self.assertEqual(start, datetime.fromisoformat("2026-09-18T08:00:00+07:00"))
        self.assertEqual(cutoff, datetime.fromisoformat("2026-09-20T09:00:00+07:00"))
        self.assertAlmostEqual((cutoff - start).total_seconds() / 3600.0, 49.0)
        self.assertEqual(cfg["timezone"], "Asia/Ho_Chi_Minh")
