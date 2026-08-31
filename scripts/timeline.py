from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta
from datetime import time as clock_time
from pathlib import Path
from typing import Any

import numpy as np
from config import REPO_ROOT, data_dir, load_config, race_window
from dem import sample_elev_xy
from ephem import night_windows, transition_events, twilight_intervals
from horizon import load_dem_array
from pace import load_anchor, load_scenarios, per_km_buckets, scenario_knots
from utils import LOOKAHEAD_M, cumulative_m, dump_json, heading_at, interp_at

from gpx import read_track

PaceKnots = list[tuple[float, datetime]]


def next_cutoff_after(prev: datetime, clock: str) -> datetime:
    parts = clock.split(":")
    hh, mm = int(parts[0]), int(parts[1])
    t = datetime.combine(prev.date(), clock_time(hh, mm), tzinfo=prev.tzinfo)
    if t <= prev:
        t += timedelta(days=1)
    return t


def load_pace_knots(path: Path, start: datetime, gpx_total_m: float) -> PaceKnots:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"no checkpoints in {path}")
    finish_km = max(float(r["cumulative_distance_km"]) for r in rows)
    if finish_km <= 0:
        raise ValueError(f"checkpoint distances are empty in {path}")
    scale = gpx_total_m / (finish_km * 1000.0)
    knots: PaceKnots = []
    prev_t = start
    for row in rows:
        km = float(row["cumulative_distance_km"])
        raw = (row.get("cutoff_time") or "").strip()
        name = (row.get("checkpoint") or "").strip().lower()
        is_start = name == "start" or km == 0.0
        if is_start and not raw:
            t = start
        elif not raw:
            continue
        else:
            t = next_cutoff_after(prev_t, raw)
        knots.append((km * 1000.0 * scale, t))
        prev_t = t
    if not knots or knots[0][0] > 0:
        knots.insert(0, (0.0, start))
    return knots


def even_pace_knots(start: datetime, cutoff: datetime, total_m: float) -> PaceKnots:
    return [(0.0, start), (total_m, cutoff)]


def time_at_dist(knots: PaceKnots, dist_m: float) -> datetime:
    t0 = knots[0][1]
    xs = [k[0] for k in knots]
    ys = [(k[1] - t0).total_seconds() for k in knots]
    d = min(max(dist_m, xs[0]), xs[-1])
    return t0 + timedelta(seconds=float(np.interp(d, xs, ys)))


def dist_at_time(knots: PaceKnots, when: datetime) -> float:
    t0 = knots[0][1]
    xs = [(k[1] - t0).total_seconds() for k in knots]
    ys = [k[0] for k in knots]
    sec = min(max((when - t0).total_seconds(), xs[0]), xs[-1])
    return float(np.interp(sec, xs, ys))


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
    nights: list[dict[str, Any]],
    knots: PaceKnots,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for night in nights:
        d0 = dist_at_time(knots, night["start"])
        d1 = dist_at_time(knots, night["end"])
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
    pace_knots: PaceKnots | None = None,
) -> list[dict[str, Any]]:
    cum = cumulative_m(lons, lats)
    total = float(cum[-1])
    if total <= 0:
        return []
    knots = pace_knots or even_pace_knots(start, cutoff, total)
    targets = list(np.arange(0.0, total, sample_m))
    if not targets or targets[-1] < total - 1.0:
        targets.append(total)
    dist = np.asarray(targets, dtype=float)
    tagged = assign_nights(dist, nights, knots)
    samples: list[dict[str, Any]] = []
    i_out = 0
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
            when = time_at_dist(knots, d)
            elapsed_h = (when - start).total_seconds() / 3600.0
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
    knots: PaceKnots,
    scenario_knots_map: dict[str, PaceKnots] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for night in nights:
        d0 = dist_at_time(knots, night["start"])
        d1 = dist_at_time(knots, night["end"])
        row: dict[str, Any] = {
            "night_id": night["night_id"],
            "start": night["start"].isoformat(),
            "end": night["end"].isoformat(),
            "label": night["label"],
            "elapsed0_h": (night["start"] - start).total_seconds() / 3600.0,
            "elapsed1_h": (night["end"] - start).total_seconds() / 3600.0,
            "dist0_km": d0 / 1000.0,
            "dist1_km": d1 / 1000.0,
            "duration_h": (night["end"] - night["start"]).total_seconds() / 3600.0,
        }
        if scenario_knots_map:
            row["scenarios"] = {
                name: {
                    "dist0_km": dist_at_time(kn, night["start"]) / 1000.0,
                    "dist1_km": dist_at_time(kn, night["end"]) / 1000.0,
                }
                for name, kn in scenario_knots_map.items()
            }
        out.append(row)
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
    scenario_knots_map: dict[str, PaceKnots] | None = None
    pace_finishes_h: dict[str, float] = {}
    pace_scenario = "realistic"
    if cfg.get("pace") and "base_pace" in (cfg.get("pace") or {}):
        if dem_array is not None and dem_transform is not None:
            elev = np.array(
                [
                    sample_elev_xy(dem_array, dem_transform, float(lon), float(lat), None)
                    for lon, lat in zip(lons, lats, strict=True)
                ],
                dtype=float,
            )
            missing = ~np.isfinite(elev)
            if np.any(missing):
                elev[missing] = eles[missing]
        else:
            elev = eles
        buckets = per_km_buckets(cumulative_m(lons, lats), elev)
        anchor = load_anchor(cfg)
        scenario_knots_map = {}
        for name, knobs in load_scenarios(cfg).items():
            kn, finish_h = scenario_knots(start, buckets, anchor, knobs)
            scenario_knots_map[name] = kn
            pace_finishes_h[name] = finish_h
        pace_scenario = str((cfg.get("pace") or {}).get("scenario") or "realistic")
        if pace_scenario not in scenario_knots_map:
            pace_scenario = "realistic"
        knots = scenario_knots_map[pace_scenario]
        pace_model = "scenarios"
    elif cfg.get("checkpoints"):
        cp_path = Path(str(cfg["checkpoints"]))
        if not cp_path.is_absolute():
            cp_path = REPO_ROOT / cp_path
        knots = load_pace_knots(cp_path, start, total_m)
        pace_model = "checkpoints"
    else:
        knots = even_pace_knots(start, cutoff, total_m)
        pace_model = "even"
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
        pace_knots=knots,
    )
    finish_h = pace_finishes_h.get(pace_scenario) or (cutoff - start).total_seconds() / 3600.0
    payload = {
        "timezone": cfg.get("timezone"),
        "start": start.isoformat(),
        "cutoff": cutoff.isoformat(),
        "length_m": total_m,
        "pace_kmh": (total_m / 1000.0) / finish_h if finish_h else None,
        "pace_model": pace_model,
        "pace_scenario": pace_scenario,
        "pace_finishes_h": pace_finishes_h,
        "observer": observer,
        "nights": enrich_nights(nights, start, knots, scenario_knots_map),
        "events": [
            {
                **e,
                "time": e["time"].isoformat(),
                "elapsed_h": (e["time"] - start).total_seconds() / 3600.0,
            }
            for e in events
        ],
    }
    dump_json(datadir / "nights.json", payload)
    dump_json(datadir / "samples.json", samples)
    print(f"{len(nights)} nights, {len(samples)} samples → {datadir}")


if __name__ == "__main__":
    main()
