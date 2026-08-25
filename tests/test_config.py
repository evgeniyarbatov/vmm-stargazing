from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from config import load_config, race_window, resolve_gpx


class TestConfig(unittest.TestCase):
    def test_repo_config_window(self) -> None:
        cfg = load_config()
        start, cutoff = race_window(cfg)
        self.assertEqual(start, datetime.fromisoformat("2026-09-18T08:00:00+07:00"))
        self.assertEqual(cutoff, datetime.fromisoformat("2026-09-20T09:00:00+07:00"))
        self.assertAlmostEqual((cutoff - start).total_seconds() / 3600.0, 49.0)
        self.assertEqual(cfg["timezone"], "Asia/Ho_Chi_Minh")

    def test_resolve_gpx_prefers_repo_then_override(self) -> None:
        cfg = load_config()
        datadir = Path(tempfile.mkdtemp())
        repo = Path(__file__).resolve().parents[1]
        found = resolve_gpx(cfg, datadir, None, repo_root=repo)
        self.assertTrue(found.is_file())
        self.assertEqual(found, repo / "gpx" / "vmm-100-miles-2026.gpx")
        override = Path(tempfile.mkdtemp()) / "other.gpx"
        override.write_text("<gpx/>", encoding="utf-8")
        self.assertEqual(resolve_gpx(cfg, datadir, override, repo_root=repo), override)
