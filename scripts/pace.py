from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import numpy as np

PaceKnots = list[tuple[float, datetime]]

DEFAULT_SCENARIOS: dict[str, dict[str, float]] = {
    "optimistic": {"terrain": 0.97, "fatigue_scale": 0.90, "extra_stoppage_h": 1.0},
    "realistic": {"terrain": 1.03, "fatigue_scale": 1.00, "extra_stoppage_h": 2.5},
    "conservative": {"terrain": 1.10, "fatigue_scale": 1.15, "extra_stoppage_h": 4.0},
}

SCENARIO_ORDER = ("optimistic", "realistic", "conservative")


def smooth_elev(elev: np.ndarray, window: int = 15) -> np.ndarray:
    z = np.asarray(elev, dtype=float)
    if window <= 1 or len(z) == 0:
        return z
    pad = window // 2
    padded = np.pad(z, (pad, pad), mode="edge")
    kernel = np.ones(window, dtype=float) / float(window)
    return np.convolve(padded, kernel, mode="valid")[: len(z)]


def per_km_buckets(
    dist_m: np.ndarray, elev_m: np.ndarray, window: int = 15
) -> list[tuple[int, float, float, float]]:
    dist_km = np.asarray(dist_m, dtype=float) / 1000.0
    elev = smooth_elev(elev_m, window)
    delta = np.diff(elev, prepend=elev[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    total = float(dist_km[-1]) if len(dist_km) else 0.0
    if total <= 0:
        return []
    whole = int(np.floor(total))
    rows: list[tuple[int, float, float, float]] = []
    for k in range(whole):
        mask = (dist_km >= k) & (dist_km < k + 1)
        rows.append((k, float(gain[mask].sum()), float(loss[mask].sum()), 1.0))
    rem = total - whole
    if rem > 1e-6:
        mask = dist_km >= whole
        rows.append((whole, float(gain[mask].sum()), float(loss[mask].sum()), rem))
    return rows


def fatigue_per_km(anchor: dict[str, float]) -> float:
    return (float(anchor["end_fatigue"]) - 1.0) / float(anchor["calib_distance_km"])


def predict_cum_h(
    buckets: list[tuple[int, float, float, float]],
    anchor: dict[str, float],
    terrain: float,
    fatigue_scale: float,
    extra_stoppage_h: float,
) -> tuple[np.ndarray, np.ndarray, float]:
    if not buckets:
        return np.zeros(0), np.zeros(0), extra_stoppage_h
    fpk = fatigue_per_km(anchor)
    km = np.array([b[0] for b in buckets], dtype=float)
    gain = np.array([b[1] for b in buckets], dtype=float)
    loss = np.array([b[2] for b in buckets], dtype=float)
    frac = np.array([b[3] for b in buckets], dtype=float)
    pace = (
        float(anchor["base_pace"])
        + gain * float(anchor["ele_penalty"])
        - loss * float(anchor["descent_benefit"])
    )
    pace = pace * (1.0 + fpk * km * fatigue_scale) * terrain
    pace = np.clip(pace, 4.0, float(anchor["max_climb_pace"]))
    moving = np.cumsum(pace * frac) / 60.0
    km_max = max(float(km[-1]), 1.0)
    cum_h = moving + extra_stoppage_h * (km / km_max)
    dist_m = (km + frac) * 1000.0
    finish_h = float(moving[-1] + extra_stoppage_h)
    return dist_m, cum_h, finish_h


def knots_from_cum_h(
    start: datetime, dist_m: np.ndarray, cum_h: np.ndarray
) -> PaceKnots:
    knots: PaceKnots = [(0.0, start)]
    for d, h in zip(dist_m, cum_h, strict=True):
        knots.append((float(d), start + timedelta(hours=float(h))))
    return knots


def scenario_knots(
    start: datetime,
    buckets: list[tuple[int, float, float, float]],
    anchor: dict[str, float],
    knobs: dict[str, float],
) -> tuple[PaceKnots, float]:
    dist_m, cum_h, finish_h = predict_cum_h(
        buckets,
        anchor,
        float(knobs["terrain"]),
        float(knobs["fatigue_scale"]),
        float(knobs["extra_stoppage_h"]),
    )
    return knots_from_cum_h(start, dist_m, cum_h), finish_h


def load_anchor(cfg: dict[str, Any]) -> dict[str, float]:
    pace = cfg.get("pace") or {}
    return {
        "max_climb_pace": float(pace.get("max_climb_pace") or 40.0),
        "base_pace": float(pace["base_pace"]),
        "ele_penalty": float(pace["ele_penalty"]),
        "descent_benefit": float(pace["descent_benefit"]),
        "end_fatigue": float(pace["end_fatigue"]),
        "calib_distance_km": float(pace["calib_distance_km"]),
    }


def load_scenarios(cfg: dict[str, Any]) -> dict[str, dict[str, float]]:
    raw = (cfg.get("pace") or {}).get("scenarios") or DEFAULT_SCENARIOS
    out: dict[str, dict[str, float]] = {}
    for name in SCENARIO_ORDER:
        kn = raw.get(name) or DEFAULT_SCENARIOS[name]
        out[name] = {
            "terrain": float(kn["terrain"]),
            "fatigue_scale": float(kn["fatigue_scale"]),
            "extra_stoppage_h": float(kn["extra_stoppage_h"]),
        }
    return out
