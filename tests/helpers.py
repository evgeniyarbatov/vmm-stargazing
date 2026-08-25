from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def write_ridge_dem(path: Path) -> Path:
    west, north = 103.8400, 22.3360
    res = 0.0002
    height, width = 50, 60
    xs = np.linspace(0, 1, width)
    ys = np.linspace(0, 1, height)
    xx, yy = np.meshgrid(xs, ys)
    z = (1500 + 250 * np.exp(-((xx - 0.5) ** 2 + (yy - 0.5) ** 2) * 12) + 100 * xx).astype(
        np.float32
    )
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": from_origin(west, north, res, res),
        "nodata": float("nan"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(z, 1)
    return path
