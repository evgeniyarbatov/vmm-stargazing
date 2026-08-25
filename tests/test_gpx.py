from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from gpx import clean_gpx, read_track
from helpers import FIXTURES


class TestGpx(unittest.TestCase):
    def test_read_ridge_fixture(self) -> None:
        lons, lats, eles, name = read_track(FIXTURES / "ridge.gpx")
        self.assertEqual(len(lons), 4)
        self.assertEqual(name, "ridge")
        self.assertAlmostEqual(float(lons[0]), 103.8410)
        self.assertAlmostEqual(float(lats[0]), 22.3330)
        self.assertAlmostEqual(float(eles[0]), 1500)

    def test_clean_writes_densified_gpx_and_bbox(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        out_gpx = tmp / "input.gpx"
        out_bbox = tmp / "bbox.json"
        clean_gpx(FIXTURES / "ridge.gpx", out_gpx, out_bbox, densify_m=20)
        lons, lats, eles, name = read_track(out_gpx)
        self.assertEqual(name, "ridge")
        self.assertGreater(len(lons), 4)
        self.assertTrue(np.isfinite(eles).all())
        bbox = json.loads(out_bbox.read_text(encoding="utf-8"))
        self.assertIn("west", bbox)
        self.assertGreater(bbox["length_m"], 500)
        self.assertEqual(bbox["n_points"], len(lons))
