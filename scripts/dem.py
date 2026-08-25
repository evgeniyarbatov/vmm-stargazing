from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import rowcol
from utils import ensure_parent, expand_bbox

StitchFn = Callable[[float, float, float, float], tuple[np.ndarray, dict]]


def load_bbox(path: Path) -> dict[str, float]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {key: float(raw[key]) for key in ("west", "south", "east", "north")}


def stitch_glo30(west: float, south: float, east: float, north: float) -> tuple[np.ndarray, dict]:
    from dem_stitcher import stitch_dem

    array, profile = stitch_dem(
        [west, south, east, north],
        dem_name="glo_30",
        dst_ellipsoidal_height=False,
    )
    return array, dict(profile)


def write_geotiff(path: Path, array: np.ndarray, profile: dict) -> None:
    ensure_parent(path)
    tmp = path.with_suffix(path.suffix + ".partial")
    with rasterio.open(tmp, "w", **profile) as dst:
        dst.write(array, 1)
    tmp.replace(path)


def fetch_dem(
    bbox: dict[str, float],
    out_path: Path,
    buffer_km: float,
    force: bool = False,
    stitch: StitchFn | None = None,
) -> Path:
    if out_path.exists() and out_path.stat().st_size > 0 and not force:
        return out_path
    padded = expand_bbox(bbox, buffer_km)
    stitch_fn = stitch or stitch_glo30
    array, profile = stitch_fn(padded["west"], padded["south"], padded["east"], padded["north"])
    write_geotiff(out_path, array, profile)
    return out_path


def sample_elev_xy(
    array: np.ndarray,
    transform: object,
    lon: float,
    lat: float,
    nodata: float | None,
) -> float:
    row, col = rowcol(transform, lon, lat, op=float)
    height, width = array.shape
    if row < 0 or col < 0 or row > height - 1 or col > width - 1:
        return float("nan")
    r0 = int(np.floor(row))
    c0 = int(np.floor(col))
    r1 = min(r0 + 1, height - 1)
    c1 = min(c0 + 1, width - 1)
    dr = row - r0
    dc = col - c0
    v00 = float(array[r0, c0])
    v01 = float(array[r0, c1])
    v10 = float(array[r1, c0])
    v11 = float(array[r1, c1])
    values = [v00, v01, v10, v11]
    bad = []
    for v in values:
        nodata_hit = nodata is not None and np.isfinite(nodata) and v == nodata
        bad.append((not np.isfinite(v)) or nodata_hit)
    if any(bad):
        finite = [v for v, is_bad in zip(values, bad, strict=True) if not is_bad]
        return float(finite[0]) if finite else float("nan")
    top = v00 * (1 - dc) + v01 * dc
    bottom = v10 * (1 - dc) + v11 * dc
    return float(top * (1 - dr) + bottom * dr)


def sample_elev(dem: rasterio.DatasetReader, lon: float, lat: float) -> float:
    return sample_elev_xy(dem.read(1), dem.transform, lon, lat, dem.nodata)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch/cache Copernicus GLO-30 for a bbox JSON.")
    parser.add_argument("bbox", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--buffer-km", type=float, default=15.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    path = fetch_dem(load_bbox(args.bbox), args.out, args.buffer_km, force=args.force)
    print(path)


if __name__ == "__main__":
    main()
