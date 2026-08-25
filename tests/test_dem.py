from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from rasterio.transform import from_origin

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from dem import fetch_dem, sample_elev_xy
from helpers import write_ridge_dem


class TestDem(unittest.TestCase):
    def test_cache_hit_skips_stitch(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        out = write_ridge_dem(tmp / "glo30.tif")
        bbox = {"west": 103.84, "south": 22.33, "east": 103.85, "north": 22.34}

        def boom(*_args: object) -> tuple[np.ndarray, dict]:
            raise AssertionError("stitch should not run on cache hit")

        path = fetch_dem(bbox, out, buffer_km=1.0, stitch=boom)
        self.assertEqual(path, out)

    def test_force_writes_new_raster(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        out = tmp / "glo30.tif"
        bbox = {"west": 103.84, "south": 22.33, "east": 103.85, "north": 22.34}
        array = np.ones((8, 8), dtype=np.float32)
        profile = {
            "driver": "GTiff",
            "height": 8,
            "width": 8,
            "count": 1,
            "dtype": "float32",
            "crs": "EPSG:4326",
            "transform": from_origin(103.84, 22.34, 0.001, 0.001),
        }

        def stitch(*_args: object) -> tuple[np.ndarray, dict]:
            return array, profile

        path = fetch_dem(bbox, out, buffer_km=0.0, stitch=stitch)
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 0)

    def test_sample_elev_on_ridge(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        path = write_ridge_dem(tmp / "dem.tif")
        import rasterio

        with rasterio.open(path) as dem:
            z = sample_elev_xy(dem.read(1), dem.transform, 103.846, 22.331, dem.nodata)
        self.assertGreater(z, 1500)
        self.assertLess(z, 2000)
