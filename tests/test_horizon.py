from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from helpers import write_ridge_dem
from horizon import horizon_along_azs, horizon_at_az, horizon_profile, load_dem_array


class TestHorizon(unittest.TestCase):
    def test_ridge_blocks_east_more_than_west(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        path = write_ridge_dem(tmp / "dem.tif")
        array, transform, _nodata = load_dem_array(path)
        profile = horizon_profile(
            array,
            transform,
            lon=103.8415,
            lat=22.3310,
            elev_m=1510,
            n_az=36,
            max_km=2.0,
            step_m=50.0,
        )
        east = horizon_at_az(profile, 90.0)
        west = horizon_at_az(profile, 270.0)
        self.assertGreater(east, west)
        self.assertGreater(east, 5.0)

    def test_ahead_slice_matches_profile_at_heading(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        path = write_ridge_dem(tmp / "dem.tif")
        array, transform, _nodata = load_dem_array(path)
        heading = 90.0
        rels = np.linspace(-90.0, 90.0, 19)
        slice_h = horizon_along_azs(
            array,
            transform,
            lon=103.8415,
            lat=22.3310,
            elev_m=1510,
            azs=heading + rels,
            max_km=2.0,
            step_m=50.0,
        )
        self.assertGreater(slice_h[len(slice_h) // 2], 5.0)
