from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from config import data_dir, load_config
from ephem import load_ephemeris, observe_all
from horizon import horizon_at_az, horizon_profile, load_dem_array
from utils import dump_json, load_json


def tag_for(alt_deg: float, az_deg: float) -> str:
    if alt_deg >= 60:
        return "overhead"
    if alt_deg < 0:
        return "down"
    if alt_deg < 25 and 0 <= az_deg < 180:
        return "rising"
    if alt_deg < 25 and az_deg >= 180:
        return "setting"
    return "up"


def annotate_row(
    row: dict[str, Any],
    profile: np.ndarray | None,
    buffer_deg: float,
    mag_limit: float,
) -> dict[str, Any] | None:
    alt = float(row["alt_deg"])
    az = float(row["az_deg"])
    horizon = horizon_at_az(profile, az) if profile is not None else 0.0
    mag = row.get("mag")
    if mag is not None and float(mag) > mag_limit and row["kind"] == "planet":
        return None
    obscured = alt < horizon + buffer_deg
    return {
        **row,
        "horizon_deg": horizon,
        "obscured": bool(obscured),
        "tag": tag_for(alt, az),
    }


def observe_samples(
    samples: list[dict[str, Any]],
    dem_path: Path | None,
    ts: Any,
    eph: Any,
    buffer_deg: float,
    mag_limit: float,
    include_moon: bool,
    include_milky_way: bool,
    max_km: float = 15.0,
) -> list[dict[str, Any]]:
    dem_array = None
    dem_transform = None
    if dem_path is not None and dem_path.is_file():
        dem_array, dem_transform, _ = load_dem_array(dem_path)
    profiles: dict[int, np.ndarray] = {}
    rows: list[dict[str, Any]] = []
    for sample in samples:
        i = int(sample["i"])
        if dem_array is not None and dem_transform is not None:
            profiles[i] = horizon_profile(
                dem_array,
                dem_transform,
                float(sample["lon"]),
                float(sample["lat"]),
                float(sample["elev_m"]),
                max_km=max_km,
            )
        when = datetime.fromisoformat(sample["time"])
        bodies = observe_all(
            ts,
            eph,
            float(sample["lat"]),
            float(sample["lon"]),
            float(sample["elev_m"]),
            when,
            include_moon=include_moon,
            include_milky_way=include_milky_way,
        )
        profile = profiles.get(i)
        for body in bodies:
            annotated = annotate_row(body, profile, buffer_deg, mag_limit)
            if annotated is None:
                continue
            rows.append(
                {
                    "sample_i": i,
                    "night_id": sample["night_id"],
                    "time": sample["time"],
                    "dist_km": sample["dist_km"],
                    **annotated,
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Planet/star/moon positions at night samples.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    datadir = data_dir(args.data_dir)
    vis = cfg.get("visibility") or {}
    samples = load_json(datadir / "samples.json")
    ts, eph = load_ephemeris(datadir / "ephemeris")
    rows = observe_samples(
        samples,
        datadir / "dem" / "glo30.tif",
        ts,
        eph,
        buffer_deg=float(vis.get("horizon_buffer_deg") or 2.0),
        mag_limit=float(vis.get("planet_mag_limit") or 6.0),
        include_moon=bool(vis.get("include_moon", True)),
        include_milky_way=bool(vis.get("include_milky_way_note", True)),
    )
    dump_json(datadir / "sky.json", rows)
    n_up = sum(1 for r in rows if r["kind"] == "planet" and r["alt_deg"] > 0 and not r["obscured"])
    print(f"{len(rows)} sky rows ({n_up} planets above terrain) → {datadir / 'sky.json'}")


if __name__ == "__main__":
    main()
