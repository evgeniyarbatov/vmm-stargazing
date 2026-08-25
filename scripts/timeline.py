from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from config import data_dir, load_config, race_window
from dem import sample_elev_xy
from ephem import night_windows, transition_events, twilight_intervals
from gpx import read_track
from horizon import load_dem_array
from utils import LOOKAHEAD_M, cumulative_m, dump_json, heading_at, interp_at


def time_at_frac(start: datetime, cutoff: datetime, frac: float) -> datetime:
    span = cutoff - start
    return start + timedelta(seconds=span.total_seconds() * min(max(frac, 0.0), 1.0))


def frac_at_time(start: datetime, cutoff: datetime, when: datetime) -> float:
    span = (cutoff - start).total_seconds()
    if span <= 0:
        return 0.0
    return min(max((when - start).total_seconds() / span, 0.0), 1.0)


def pick_indices(n: int, cap: int) -> list[int]:
    if n <= cap:
        return list(range(n))
    raw = np.linspace(0, n - 1, cap)
    idx = [int(round(x)) for x in raw]
    out: list[int] = []
    for i in idx:
        if not out or i != out[-1]:
            out.append(i)
    if out[0] != 0:
        out[0] = 0
    if out[-1] != n - 1:
        out[-1] = n - 1
    return out


def assign_nights(
    dist: np.ndarray,
    start: datetime,
    cutoff: datetime,
    nights: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    total = float(dist[-1]) if len(dist) else 0.0
    rows: list[dict[str, Any]] = []
    for night in nights:
        t0, t1 = night["start"], night["end"]
        d0 = frac_at_time(start, cutoff, t0) * total
        d1 = frac_at_time(start, cutoff, t1) * total
        mask = (dist >= d0) & (dist <= d1)
        idxs = np.nonzero(mask)[0]
        rows.append({**night, "dist0_m": d0, "dist1_m": d1, "sample_idx": idxs})
    return rows


def build_samples(
    lons: np.ndarray,
    lats: np.ndarray,
    gpx_eles: np.ndarray,
    dem_array: np.ndarray | None,
    dem_transform: object | None,
    start: datetime,
    cutoff: datetime,
    nights: list[dict[str, Any]],
    sample_m: float,
    max_per_night: int,
    fallback_elev: float,
) -> list[dict[str, Any]]:
    cum = cumulative_m(lons, lats)
    total = float(cum[-1])
    if total <= 0:
        return []
    targets = list(np.arange(0.0, total, sample_m))
    if not targets or targets[-1] < total - 1.0:
        targets.append(total)
    dist = np.asarray(targets, dtype=float)
    tagged = assign_nights(dist, start, cutoff, nights)
    samples: list[dict[str, Any]] = []
    i_out = 0
    span_s = (cutoff - start).total_seconds()
    for night in tagged:
        idxs = list(night["sample_idx"])
        d0 = float(night["dist0_m"])
        d1 = float(night["dist1_m"])
        chosen_d = sorted({d0, d1, *[float(dist[j]) for j in idxs]})
        keep_d = [chosen_d[k] for k in pick_indices(len(chosen_d), max_per_night)]
        for d in keep_d:
            lon, lat = interp_at(lons, lats, d)
            elev = fallback_elev
            if dem_array is not None and dem_transform is not None:
                z = sample_elev_xy(dem_array, dem_transform, lon, lat, None)
                if np.isfinite(z):
                    elev = float(z)
            else:
                gpx_z = float(np.interp(d, cum, gpx_eles))
                if np.isfinite(gpx_z):
                    elev = gpx_z
            elapsed_h = (d / total) * span_s / 3600.0 if total else 0.0
            when = time_at_frac(start, cutoff, d / total if total else 0.0)
            samples.append(
                {
                    "i": i_out,
                    "night_id": night["night_id"],
                    "dist_m": d,
                    "dist_km": d / 1000.0,
                    "lon": lon,
                    "lat": lat,
                    "elev_m": elev,
                    "heading_deg": heading_at(lons, lats, d, LOOKAHEAD_M, total),
                    "elapsed_h": elapsed_h,
                    "time": when.isoformat(),
                }
            )
            i_out += 1
    return samples


def enrich_nights(
    nights: list[dict[str, Any]],
    start: datetime,
    cutoff: datetime,
    total_m: float,
) -> list[dict[str, Any]]:
    span_h = (cutoff - start).total_seconds() / 3600.0
    out: list[dict[str, Any]] = []
    for night in nights:
        d0 = frac_at_time(start, cutoff, night["start"]) * total_m
        d1 = frac_at_time(start, cutoff, night["end"]) * total_m
        out.append(
            {
                "night_id": night["night_id"],
                "start": night["start"].isoformat(),
                "end": night["end"].isoformat(),
                "label": night["label"],
                "elapsed0_h": frac_at_time(start, cutoff, night["start"]) * span_h,
                "elapsed1_h": frac_at_time(start, cutoff, night["end"]) * span_h,
                "dist0_km": d0 / 1000.0,
                "dist1_km": d1 / 1000.0,
                "duration_h": (night["end"] - night["start"]).total_seconds() / 3600.0,
            }
        )
    return out


def mean_observer(
    lons: np.ndarray,
    lats: np.ndarray,
    dem_array: np.ndarray | None,
    dem_transform: object | None,
    fallback_elev: float,
) -> dict[str, float]:
    lon = float(np.mean(lons))
    lat = float(np.mean(lats))
    elev = fallback_elev
    if dem_array is not None and dem_transform is not None:
        z = sample_elev_xy(dem_array, dem_transform, lon, lat, None)
        if np.isfinite(z):
            elev = float(z)
    return {"lon": lon, "lat": lat, "elev_m": elev}


def main() -> None:
    parser = argparse.ArgumentParser(description="Night windows and along-track night samples.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--sample-m", type=float, default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    datadir = data_dir(args.data_dir)
    start, cutoff = race_window(cfg)
    sampling = cfg.get("sampling") or {}
    sample_m = float(args.sample_m or sampling.get("distance_m") or 2000)
    max_per_night = int(sampling.get("max_points_per_night") or 12)
    race = cfg.get("race") or {}
    fallback_elev = float(race.get("default_elev_m") or 1500)

    lons, lats, eles, _name = read_track(datadir / "input.gpx")
    total_m = float(cumulative_m(lons, lats)[-1])
    dem_path = datadir / "dem" / "glo30.tif"
    dem_array: np.ndarray | None = None
    dem_transform: object | None = None
    if dem_path.is_file():
        dem_array, dem_transform, _nodata = load_dem_array(dem_path)

    observer = mean_observer(lons, lats, dem_array, dem_transform, fallback_elev)
    from ephem import load_ephemeris

    ts, eph = load_ephemeris(datadir / "ephemeris")
    intervals = twilight_intervals(
        ts, eph, observer["lat"], observer["lon"], observer["elev_m"], start, cutoff
    )
    nights = night_windows(intervals)
    events = transition_events(intervals)
    samples = build_samples(
        lons,
        lats,
        eles,
        dem_array,
        dem_transform,
        start,
        cutoff,
        nights,
        sample_m,
        max_per_night,
        fallback_elev,
    )
    payload = {
        "timezone": cfg.get("timezone"),
        "start": start.isoformat(),
        "cutoff": cutoff.isoformat(),
        "length_m": total_m,
        "pace_kmh": (total_m / 1000.0) / ((cutoff - start).total_seconds() / 3600.0),
        "observer": observer,
        "nights": enrich_nights(nights, start, cutoff, total_m),
        "events": [
            {
                **e,
                "time": e["time"].isoformat(),
                "elapsed_h": frac_at_time(start, cutoff, e["time"])
                * ((cutoff - start).total_seconds() / 3600.0),
            }
            for e in events
        ],
    }
    dump_json(datadir / "nights.json", payload)
    dump_json(datadir / "samples.json", samples)
    print(f"{len(nights)} nights, {len(samples)} samples → {datadir}")


if __name__ == "__main__":
    main()
