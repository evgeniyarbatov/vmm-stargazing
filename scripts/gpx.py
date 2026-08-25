from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import gpxpy
import gpxpy.gpx
import numpy as np
from config import data_dir, load_config, resolve_gpx
from utils import bbox_of, densify_track, dump_json, ensure_parent, segment_lengths_m


def read_track(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    with path.open(encoding="utf-8") as handle:
        gpx = gpxpy.parse(handle)
    lons: list[float] = []
    lats: list[float] = []
    eles: list[float] = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                lons.append(point.longitude)
                lats.append(point.latitude)
                eles.append(float(point.elevation) if point.elevation is not None else float("nan"))
    if not lons:
        for route in gpx.routes:
            for point in route.points:
                lons.append(point.longitude)
                lats.append(point.latitude)
                eles.append(float(point.elevation) if point.elevation is not None else float("nan"))
    if len(lons) < 2:
        raise ValueError(f"Need at least 2 track/route points in {path}")
    name = ""
    if gpx.tracks and gpx.tracks[0].name:
        name = gpx.tracks[0].name
    elif gpx.name:
        name = gpx.name
    elif gpx.routes and gpx.routes[0].name:
        name = gpx.routes[0].name
    return (
        np.asarray(lons, dtype=float),
        np.asarray(lats, dtype=float),
        np.asarray(eles, dtype=float),
        name,
    )


def read_lon_lat(path: Path) -> tuple[np.ndarray, np.ndarray, str]:
    lons, lats, _eles, name = read_track(path)
    return lons, lats, name


def write_cleaned_gpx(
    path: Path,
    lons: np.ndarray,
    lats: np.ndarray,
    eles: np.ndarray,
    name: str,
) -> None:
    gpx = gpxpy.gpx.GPX()
    track = gpxpy.gpx.GPXTrack(name=name or path.stem)
    segment = gpxpy.gpx.GPXTrackSegment()
    for lon, lat, ele in zip(lons, lats, eles, strict=True):
        pt = gpxpy.gpx.GPXTrackPoint(latitude=float(lat), longitude=float(lon))
        if np.isfinite(ele):
            pt.elevation = float(ele)
        segment.points.append(pt)
    track.segments.append(segment)
    gpx.tracks.append(track)
    ensure_parent(path)
    path.write_text(gpx.to_xml(), encoding="utf-8")


def write_bbox(
    path: Path,
    lons: np.ndarray,
    lats: np.ndarray,
) -> dict[str, float | int]:
    box = bbox_of(lons, lats)
    payload: dict[str, float | int] = {
        **box,
        "n_points": int(len(lons)),
        "length_m": float(segment_lengths_m(lons, lats).sum()),
    }
    dump_json(path, payload)
    return payload


def copy_source(src: Path, dest: Path) -> None:
    if src.resolve() == dest.resolve():
        return
    ensure_parent(dest)
    shutil.copy2(src, dest)


def clean_gpx(src: Path, out_gpx: Path, out_bbox: Path, densify_m: float) -> None:
    lons, lats, eles, name = read_track(src)
    dense_lon, dense_lat, dense_ele = densify_track(lons, lats, eles, densify_m)
    write_cleaned_gpx(out_gpx, dense_lon, dense_lat, dense_ele, name)
    write_bbox(out_bbox, dense_lon, dense_lat)


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy, clean, and densify the race GPX.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--gpx", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--densify-m", type=float, default=10.0)
    args = parser.parse_args()
    cfg = load_config(args.config)
    datadir = data_dir(args.data_dir)
    src = resolve_gpx(cfg, datadir, args.gpx)
    if not src.is_file():
        raise SystemExit(f"Error: GPX file not found: {src}")
    dest = datadir / str(cfg["gpx"])
    copy_source(src, dest)
    clean_gpx(dest, datadir / "input.gpx", datadir / "bbox.json", args.densify_m)
    print(datadir / "input.gpx")


if __name__ == "__main__":
    main()
