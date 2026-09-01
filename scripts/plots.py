from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np
from catalog import NAV_STARS
from config import REPO_ROOT, data_dir, load_config
from horizon import horizon_along_azs, horizon_at_az, horizon_profile, load_dem_array
from report import altitude_stem, fmt_hours, fmt_time, rows_for_sample, sample_stem
from utils import dump_json, ensure_parent, load_json, sample_along

from gpx import read_track, write_spots_gpx

PAPER = "#ffffff"
INK = "#1e1e2e"
MUTED = "#6c6f85"
GRID = "#ccd0da"
SPINE = "#bcc0cc"
HORIZON_FILL = "#e6e9ef"
HORIZON_LINE = "#8c8fa1"
DAY_TRACK = "#fe640b"
RUN = "#d20f39"
GUIDE = "#df8e1d"
MOON = "#dc8a78"
MW = "#8839ef"
STAR = "#1e1e2e"
AHEAD_DEG = 20.0
AHEAD_HALF_DEG = 90.0
OPEN_REF_DEG = 45.0
LOCAL_PEAK_BUMP = 0.08
SPOT_GAP_KM = 4.0
SPOT_MAX_PER_NIGHT = 8
SPOT_SCORE_FLOOR = 0.7
NIGHT_COLORS = {1: "#1e66f5", 2: "#8839ef", 3: "#40a02b"}
PLANET_COLORS = {
    "Mercury": "#7c7f93",
    "Venus": "#df8e1d",
    "Mars": "#d20f39",
    "Jupiter": "#fe640b",
    "Saturn": "#179299",
}
STAR_PALETTE = (
    "#1e66f5",
    "#d20f39",
    "#40a02b",
    "#df8e1d",
    "#8839ef",
    "#fe640b",
    "#179299",
    "#e64553",
    "#04a5e5",
    "#ea76cb",
    "#4a7c2c",
    "#9d6b3a",
    "#7287fd",
    "#00a86b",
    "#c6a645",
    "#6c2c6f",
    "#dd7878",
    "#1e1e2e",
)


def altaz_to_rtheta(alt_deg: float, az_deg: float) -> tuple[float, float]:
    return 90.0 - float(alt_deg), np.radians(float(az_deg) % 360.0)


def star_color(name: str) -> str:
    names = sorted(NAV_STARS)
    if name not in names:
        return STAR
    return STAR_PALETTE[names.index(name) % len(STAR_PALETTE)]


def hillshade(z: np.ndarray, azimuth: float = 315.0, altitude: float = 45.0) -> np.ndarray:
    dy, dx = np.gradient(np.asarray(z, dtype=float))
    slope = np.pi / 2.0 - np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    az = np.radians(azimuth)
    alt = np.radians(altitude)
    shade = np.sin(alt) * np.sin(slope) + np.cos(alt) * np.cos(slope) * np.cos(az - aspect)
    return (shade - shade.min()) / max(float(shade.max() - shade.min()), 1e-6)


def rel_bearing_deg(az_deg: float, heading_deg: float) -> float:
    return (float(az_deg) - float(heading_deg) + 180.0) % 360.0 - 180.0


def guide_star(sample: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    heading = float(sample.get("heading_deg") or 0.0)
    visible: list[dict[str, Any]] = []
    for row in rows:
        if row["kind"] != "star" or row["name"] not in NAV_STARS:
            continue
        if float(row["alt_deg"]) < 5.0 or row.get("obscured"):
            continue
        visible.append({**row, "rel_deg": rel_bearing_deg(row["az_deg"], heading)})
    if not visible:
        return None
    ahead = [row for row in visible if abs(float(row["rel_deg"])) <= AHEAD_DEG]
    if ahead:
        return min(
            ahead,
            key=lambda row: (
                float(row["mag"]) if row.get("mag") is not None else 99.0,
                abs(float(row["rel_deg"])),
            ),
        )
    high = [row for row in visible if float(row["alt_deg"]) > 15.0]
    pool = high or visible
    return min(pool, key=lambda row: abs(float(row["rel_deg"])))


def guide_label(row: dict[str, Any] | None) -> str:
    if row is None:
        return "—"
    rel = float(row["rel_deg"])
    if abs(rel) < 3.0:
        return f"{row['name']} ahead"
    side = "R" if rel > 0 else "L"
    return f"{row['name']} {abs(rel):.0f}° {side}"


def _mean_horizon(
    profile: np.ndarray | None,
    rows: list[dict[str, Any]],
    heading_deg: float | None = None,
    half_deg: float | None = None,
) -> float:
    if profile is not None and len(profile) > 0:
        if heading_deg is None or half_deg is None:
            return float(np.mean(profile))
        n = len(profile)
        azs = np.arange(n, dtype=float) * (360.0 / n)
        rel = (azs - float(heading_deg) + 180.0) % 360.0 - 180.0
        mask = np.abs(rel) <= float(half_deg)
        if np.any(mask):
            return float(np.mean(profile[mask]))
        return float(np.mean(profile))
    vals: list[float] = []
    for row in rows:
        if row.get("horizon_deg") is None:
            continue
        if heading_deg is not None and half_deg is not None:
            az = row.get("az_deg")
            if az is None or abs(rel_bearing_deg(az, heading_deg)) > half_deg:
                continue
        vals.append(float(row["horizon_deg"]))
    return float(np.mean(vals)) if vals else 0.0


def _open_fraction(mean_horizon_deg: float) -> float:
    return 1.0 - min(max(mean_horizon_deg / OPEN_REF_DEG, 0.0), 1.0)


def _local_elev_peaks(samples: list[dict[str, Any]]) -> set[int]:
    ordered = sorted(samples, key=lambda row: float(row["dist_km"]))
    peaks: set[int] = set()
    for i, sample in enumerate(ordered):
        elev = float(sample["elev_m"])
        if i and elev < float(ordered[i - 1]["elev_m"]):
            continue
        if i + 1 < len(ordered) and elev < float(ordered[i + 1]["elev_m"]):
            continue
        peaks.add(int(sample["i"]))
    return peaks


def score_sample(
    sample: dict[str, Any],
    rows: list[dict[str, Any]],
    profile: np.ndarray | None,
    elev_min: float,
    elev_max: float,
    local_peak: bool = False,
) -> dict[str, Any]:
    heading = sample.get("heading_deg")
    heading_f = float(heading) if heading is not None else None
    open_full = _open_fraction(_mean_horizon(profile, rows))
    if heading_f is None:
        open_ahead = open_full
        open_sky = open_full
    else:
        open_ahead = _open_fraction(
            _mean_horizon(profile, rows, heading_f, AHEAD_HALF_DEG)
        )
        open_sky = 0.5 * open_full + 0.5 * open_ahead
    span = max(elev_max - elev_min, 1.0)
    elev_score = (float(sample["elev_m"]) - elev_min) / span
    if local_peak:
        elev_score = min(1.0, elev_score + LOCAL_PEAK_BUMP)
    moons = [r for r in rows if r["kind"] == "moon"]
    if not moons or float(moons[0]["alt_deg"]) < 0 or moons[0].get("obscured"):
        moon_penalty = 0.0
    else:
        illum = float(moons[0].get("illumination") or 0.0)
        moon_penalty = min(illum * max(0.0, float(moons[0]["alt_deg"]) / 60.0), 1.0)
    mw = [r for r in rows if r["kind"] == "feature" and r["name"] == "Milky Way centre"]
    mw_up = bool(mw) and float(mw[0]["alt_deg"]) >= 0 and not mw[0].get("obscured")
    score = 0.45 * open_sky + 0.25 * elev_score + 0.15 * (1.0 - moon_penalty) + 0.15 * float(mw_up)
    return {
        "i": sample["i"],
        "night_id": sample["night_id"],
        "lon": sample["lon"],
        "lat": sample["lat"],
        "dist_km": sample["dist_km"],
        "elev_m": sample["elev_m"],
        "time": sample["time"],
        "score": score,
        "open_sky": open_sky,
        "open_ahead": open_ahead,
        "elev_score": elev_score,
        "moon_penalty": moon_penalty,
        "mw_bonus": float(mw_up),
        "local_peak": local_peak,
    }


def score_samples(
    samples: list[dict[str, Any]],
    sky: list[dict[str, Any]],
    profiles: dict[int, np.ndarray],
) -> list[dict[str, Any]]:
    by_night: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        by_night[int(sample["night_id"])].append(sample)
    out: list[dict[str, Any]] = []
    for nid in sorted(by_night):
        group = by_night[nid]
        elevs = [float(s["elev_m"]) for s in group]
        elev_min = min(elevs) if elevs else 0.0
        elev_max = max(elevs) if elevs else 1.0
        peaks = _local_elev_peaks(group)
        for sample in group:
            out.append(
                score_sample(
                    sample,
                    rows_for_sample(sky, sample["i"]),
                    profiles.get(int(sample["i"])),
                    elev_min,
                    elev_max,
                    local_peak=int(sample["i"]) in peaks,
                )
            )
    return out


def pick_best_spots(
    scores: list[dict[str, Any]],
    min_gap_km: float = SPOT_GAP_KM,
    max_per_night: int = SPOT_MAX_PER_NIGHT,
    score_floor: float = SPOT_SCORE_FLOOR,
) -> list[dict[str, Any]]:
    by_night: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in scores:
        by_night[int(row["night_id"])].append(row)
    picked: list[dict[str, Any]] = []
    for nid in sorted(by_night):
        ordered = sorted(by_night[nid], key=lambda row: float(row["dist_km"]))
        night_best = max(float(row["score"]) for row in ordered)
        floor = score_floor * night_best
        chosen: list[dict[str, Any]] = []
        remaining = list(ordered)
        while remaining and len(chosen) < max_per_night:
            origin = float(remaining[0]["dist_km"])
            window = [row for row in remaining if float(row["dist_km"]) < origin + min_gap_km]
            candidate = max(window, key=lambda row: float(row["score"]))
            if float(candidate["score"]) >= floor:
                chosen.append(candidate)
                cut = float(candidate["dist_km"]) + min_gap_km
            else:
                cut = origin + min_gap_km
            remaining = [row for row in remaining if float(row["dist_km"]) >= cut]
        picked.extend(chosen)
    return picked


def best_spots(scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return pick_best_spots(scores)


def _style_axes(ax: Any, title: str | None = None) -> None:
    ax.set_facecolor(PAPER)
    ax.tick_params(colors=INK)
    ax.xaxis.label.set_color(INK)
    ax.yaxis.label.set_color(INK)
    for spine in ax.spines.values():
        spine.set_color(SPINE)
    if title:
        ax.set_title(title, color=INK)


def _legend(ax: Any, **kwargs: Any) -> None:
    kwargs.setdefault("fontsize", 8)
    kwargs.setdefault("framealpha", 1.0)
    leg = ax.legend(**kwargs)
    frame = leg.get_frame()
    frame.set_facecolor(PAPER)
    frame.set_edgecolor(SPINE)
    for text in leg.get_texts():
        text.set_color(INK)


def _annotate(ax: Any, text: str, xy: tuple[float, float], **kwargs: Any) -> None:
    kwargs.setdefault("fontsize", 7)
    kwargs.setdefault("color", INK)
    kwargs.setdefault("zorder", 5)
    kwargs.setdefault("textcoords", "offset points")
    kwargs.setdefault("xytext", (6, 6))
    kwargs.setdefault(
        "bbox",
        {"facecolor": PAPER, "edgecolor": "none", "alpha": 0.8, "pad": 1.4},
    )
    ax.annotate(text, xy, **kwargs)


def _edge_samples(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_night: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        by_night[int(sample["night_id"])].append(sample)
    out: list[dict[str, Any]] = []
    for nid in sorted(by_night):
        group = by_night[nid]
        out.append(group[0])
        if group[-1]["i"] != group[0]["i"]:
            out.append(group[-1])
    return out


def _savefig(fig: plt.Figure, path: Path) -> Path:
    ensure_parent(path)
    fig.savefig(path, dpi=140, bbox_inches="tight", facecolor=PAPER, edgecolor="none")
    plt.close(fig)
    return path


def _draw_hillshade(ax: Any, dem_array: np.ndarray, dem_transform: Any) -> None:
    h, w = dem_array.shape
    west = dem_transform.c
    north = dem_transform.f
    east = west + dem_transform.a * w
    south = north + dem_transform.e * h
    ax.imshow(
        hillshade(dem_array),
        extent=(west, east, south, north),
        origin="upper",
        cmap="gray",
        interpolation="bilinear",
        vmin=0.15,
        vmax=1.0,
    )


def _draw_course_track(
    ax: Any,
    lons: np.ndarray,
    lats: np.ndarray,
    dist: np.ndarray,
    nights: dict[str, Any],
) -> None:
    ax.plot(lons, lats, color=DAY_TRACK, lw=1.0, zorder=2, label="day")
    for night in nights.get("nights") or []:
        nid = int(night["night_id"])
        mask = (dist >= float(night["dist0_km"]) * 1000.0) & (
            dist <= float(night["dist1_km"]) * 1000.0
        )
        ax.plot(
            lons[mask],
            lats[mask],
            color=NIGHT_COLORS.get(nid, "#ea76cb"),
            lw=2.2,
            zorder=3,
            label=f"night {nid}",
        )


def _score_limits(vals: list[float]) -> tuple[float, float]:
    if not vals:
        return 0.0, 1.0
    lo, hi = min(vals), max(vals)
    if hi - lo < 0.12:
        mid = (lo + hi) / 2.0
        lo, hi = mid - 0.06, mid + 0.06
    return lo, hi


def _night_spans(ax: Any, nights: dict[str, Any]) -> None:
    for night in nights.get("nights") or []:
        nid = int(night["night_id"])
        ax.axvspan(
            float(night["dist0_km"]),
            float(night["dist1_km"]),
            color=NIGHT_COLORS.get(nid, "#ea76cb"),
            alpha=0.18,
            label=f"night {nid}",
        )


def _horizon_profiles(
    samples: list[dict[str, Any]],
    dem_array: np.ndarray | None,
    dem_transform: Any,
) -> dict[int, np.ndarray]:
    profiles: dict[int, np.ndarray] = {}
    if dem_array is None or dem_transform is None:
        return profiles
    for sample in samples:
        profiles[int(sample["i"])] = horizon_profile(
            dem_array,
            dem_transform,
            float(sample["lon"]),
            float(sample["lat"]),
            float(sample["elev_m"]),
            n_az=72,
            max_km=15.0,
            step_m=200.0,
        )
    return profiles


def plot_course(
    path: Path,
    lons: np.ndarray,
    lats: np.ndarray,
    dist: np.ndarray,
    nights: dict[str, Any],
    samples: list[dict[str, Any]],
    dem_array: np.ndarray | None,
    dem_transform: Any,
    featured: list[dict[str, Any]] | None = None,
    highlight_i: int | None = None,
) -> Path:
    fig, ax = plt.subplots(figsize=(8.5, 8.5), facecolor=PAPER)
    if dem_array is not None and dem_transform is not None:
        _draw_hillshade(ax, dem_array, dem_transform)
    _draw_course_track(ax, lons, lats, dist, nights)
    labeled = list(featured) if featured else _edge_samples(samples)
    labeled_ids = {int(s["i"]) for s in labeled}
    for sample in samples:
        sid = int(sample["i"])
        is_hi = highlight_i is not None and sid == int(highlight_i)
        is_mark = sid in labeled_ids
        color = RUN if is_hi else NIGHT_COLORS.get(int(sample["night_id"]), "#ea76cb")
        ax.scatter(
            sample["lon"],
            sample["lat"],
            s=90 if is_hi else (28 if is_mark else 10),
            c=color,
            edgecolors=INK,
            linewidths=0.5 if is_hi else 0.4,
            zorder=6 if is_hi else 4,
        )
        if is_hi:
            ax.scatter(
                sample["lon"],
                sample["lat"],
                s=160,
                facecolors="none",
                edgecolors=RUN,
                linewidths=1.8,
                zorder=7,
            )
        if is_mark:
            text = f"{sample['dist_km']:.0f} km"
            if is_hi:
                text = f"{text}\n{fmt_time(sample['time'])}"
            _annotate(ax, text, (sample["lon"], sample["lat"]))
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("lon")
    ax.set_ylabel("lat")
    title = "Stargazing stops on course (realistic pace)"
    if highlight_i is not None:
        title = "This stop on the course (realistic pace)"
    _style_axes(ax, title)
    _legend(ax, loc="upper right")
    return _savefig(fig, path)


def plot_profile(
    path: Path,
    dist: np.ndarray,
    elev: np.ndarray,
    nights: dict[str, Any],
    samples: list[dict[str, Any]],
    featured: list[dict[str, Any]] | None = None,
) -> Path:
    fig, ax = plt.subplots(figsize=(10, 3.8), facecolor=PAPER)
    km = dist / 1000.0
    ax.plot(km, elev, color=INK, lw=1.1)
    _night_spans(ax, nights)
    marks = list(featured) if featured else _edge_samples(samples)
    for sample in marks:
        ax.scatter(sample["dist_km"], sample["elev_m"], c=INK, s=18, zorder=3)
        _annotate(
            ax,
            f"{sample['dist_km']:.0f} km",
            (sample["dist_km"], sample["elev_m"]),
            xytext=(4, 6),
        )
    ax.set_xlabel("km")
    ax.set_ylabel("elev m")
    _style_axes(ax, "Elevation · shaded = astronomical night at realistic pace")
    _legend(ax, loc="upper right")
    ax.set_xlim(float(km[0]), float(km[-1]))
    return _savefig(fig, path)


def plot_spots(
    path: Path,
    lons: np.ndarray,
    lats: np.ndarray,
    dist: np.ndarray,
    elev: np.ndarray,
    nights: dict[str, Any],
    scores: list[dict[str, Any]],
    dem_array: np.ndarray | None,
    dem_transform: Any,
) -> Path:
    fig, (ax_map, ax_prof) = plt.subplots(
        2,
        1,
        figsize=(8.5, 10.2),
        facecolor=PAPER,
        gridspec_kw={"height_ratios": [3.2, 1.5]},
    )
    if dem_array is not None and dem_transform is not None:
        _draw_hillshade(ax_map, dem_array, dem_transform)
    _draw_course_track(ax_map, lons, lats, dist, nights)
    vals = [float(s["score"]) for s in scores]
    vmin, vmax = _score_limits(vals)
    sc = ax_map.scatter(
        [s["lon"] for s in scores],
        [s["lat"] for s in scores],
        c=vals,
        s=[18 + 70 * v for v in vals],
        cmap="YlOrRd",
        vmin=vmin,
        vmax=vmax,
        edgecolors=INK,
        linewidths=0.4,
        zorder=4,
    )
    labeled = best_spots(scores)
    for row in labeled:
        _annotate(
            ax_map,
            f"{row['dist_km']:.0f} km · {row['score']:.2f}",
            (row["lon"], row["lat"]),
        )
    ax_map.set_aspect("equal", adjustable="box")
    ax_map.set_xlabel("lon")
    ax_map.set_ylabel("lat")
    _style_axes(ax_map, "Stargazing spots (realistic-pace night samples)")
    _legend(ax_map, loc="upper right")
    cb = fig.colorbar(sc, ax=ax_map, fraction=0.046, pad=0.04)
    cb.set_label("spot score", color=INK)
    cb.ax.tick_params(colors=INK)
    cb.outline.set_edgecolor(SPINE)

    km = dist / 1000.0
    ax_prof.plot(km, elev, color=INK, lw=1.0)
    _night_spans(ax_prof, nights)
    ax_prof.scatter(
        [s["dist_km"] for s in scores],
        [s["elev_m"] for s in scores],
        c=vals,
        s=[18 + 50 * v for v in vals],
        cmap="YlOrRd",
        vmin=vmin,
        vmax=vmax,
        edgecolors=INK,
        linewidths=0.4,
        zorder=4,
    )
    ax_prof.set_xlabel("km")
    ax_prof.set_ylabel("elev m")
    _style_axes(ax_prof)
    ax_prof.set_xlim(float(km[0]), float(km[-1]))
    if ax_prof.get_legend() is None and (nights.get("nights") or []):
        _legend(ax_prof, loc="upper right")
    return _savefig(fig, path)


def plot_sky_disc(
    path: Path,
    sample: dict[str, Any],
    rows: list[dict[str, Any]],
    profile: np.ndarray | None,
    guide: dict[str, Any] | None = None,
) -> Path:
    fig = plt.figure(figsize=(7.2, 7.6), facecolor=PAPER)
    ax = fig.add_subplot(111, projection="polar")
    ax.set_facecolor(PAPER)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 90)
    ax.set_yticks([30, 60, 90])
    ax.set_yticklabels(["60°", "30°", "horizon"], color=MUTED, fontsize=8)
    ax.set_xticks(np.radians([0, 90, 180, 270]))
    ax.set_xticklabels(["N", "E", "S", "W"], color=INK)
    ax.grid(color=GRID, lw=0.6)
    ax.spines["polar"].set_color(SPINE)

    if profile is not None:
        az = np.linspace(0.0, 360.0, 361)
        r_h = np.clip([90.0 - horizon_at_az(profile, a) for a in az], 0.0, 90.0)
        theta = np.radians(az)
        ax.fill_between(theta, r_h, 90.0, color=HORIZON_FILL, alpha=0.95, zorder=1)
        ax.plot(theta, r_h, color=HORIZON_LINE, lw=0.9, zorder=2)

    heading = float(sample.get("heading_deg") or 0.0)
    theta_h = np.radians(heading)
    ax.plot([theta_h, theta_h], [0, 90], color=RUN, lw=0.6, ls="--", alpha=0.4, zorder=3)
    ax.annotate(
        "",
        xy=(theta_h, 88),
        xytext=(theta_h, 72),
        arrowprops={"arrowstyle": "->", "color": RUN, "lw": 1.6},
        zorder=6,
    )
    ax.text(theta_h, 62, "run", color=RUN, ha="center", va="center", fontsize=8)

    guide_name = guide["name"] if guide else None
    for row in rows:
        alt = float(row["alt_deg"])
        if alt < 0:
            continue
        r, theta = altaz_to_rtheta(alt, float(row["az_deg"]))
        kind = row["kind"]
        obscured = bool(row.get("obscured"))
        name = row["name"]
        if kind == "planet":
            color = PLANET_COLORS.get(name, INK)
            ax.scatter(
                theta,
                r,
                s=90,
                c=color if not obscured else "none",
                edgecolors=color,
                linewidths=1.2,
                zorder=5,
                alpha=0.35 if obscured else 1.0,
            )
            ax.annotate(
                name,
                (theta, r),
                textcoords="offset points",
                xytext=(5, 5),
                color=color,
                fontsize=8,
            )
        elif kind == "moon":
            ax.scatter(theta, r, s=160, c=MOON, edgecolors=INK, zorder=5)
            ax.annotate(
                "Moon",
                (theta, r),
                textcoords="offset points",
                xytext=(6, 6),
                color=MOON,
                fontsize=8,
            )
        elif kind == "feature":
            ax.scatter(theta, r, s=70, marker="*", c=MW, zorder=5)
            ax.annotate(
                "MW", (theta, r), textcoords="offset points", xytext=(5, 5), color=MW, fontsize=8
            )
        elif kind == "star" and name in NAV_STARS and alt >= 5:
            mag = float(row["mag"]) if row.get("mag") is not None else 2.0
            size = max(8.0, 55.0 * 0.65**mag)
            is_guide = name == guide_name
            color = star_color(name)
            ax.scatter(
                theta,
                r,
                s=size * (1.6 if is_guide else 1.0),
                c=color,
                zorder=4,
                alpha=0.25 if obscured else 0.95,
            )
            if is_guide:
                ax.scatter(
                    theta,
                    r,
                    s=size * 4.0,
                    facecolors="none",
                    edgecolors=GUIDE,
                    linewidths=1.3,
                    zorder=5,
                )
            if (mag <= 1.3 or is_guide) and not obscured:
                label = f"{name} · ahead" if is_guide else name
                ax.annotate(
                    label,
                    (theta, r),
                    textcoords="offset points",
                    xytext=(4, 4),
                    color=GUIDE if is_guide else color,
                    fontsize=7,
                )

    title = (
        f"{fmt_time(sample['time'])}  ·  km {sample['dist_km']:.1f}  ·  "
        f"{fmt_hours(sample['elapsed_h'])}"
    )
    ax.set_title(title, color=INK, pad=12, fontsize=10)
    fig.text(
        0.5,
        0.02,
        "zenith centre · north up · filled edge = terrain · gold ring = ahead",
        ha="center",
        color=MUTED,
        fontsize=8,
    )
    return _savefig(fig, path)


def _altitude_targets(
    series: str, samples: list[dict[str, Any]], sky: list[dict[str, Any]]
) -> list[tuple[str, str]]:
    ids = {s["i"] for s in samples}
    if series == "planets":
        return [("planet", n) for n in PLANET_COLORS] + [("moon", "Moon")]
    up = {
        r["name"]
        for r in sky
        if r["kind"] == "star"
        and r["name"] in NAV_STARS
        and r["sample_i"] in ids
        and float(r["alt_deg"]) > 5
    }
    return [("star", n) for n in sorted(up)]


def _series_color(kind: str, name: str) -> str:
    if kind == "star":
        return star_color(name)
    if kind == "moon":
        return MOON
    return PLANET_COLORS.get(name, INK)


def _local_time(value: str | datetime) -> datetime:
    dt = datetime.fromisoformat(value) if isinstance(value, str) else value
    return dt.replace(tzinfo=None)


def _clock_axis(ax: Any, span: list[datetime]) -> None:
    if span:
        ax.set_xlim(min(span), max(span))
    ax.xaxis.set_major_locator(mdates.HourLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))


def _body_altitude(
    samples: list[dict[str, Any]], sky: list[dict[str, Any]], kind: str, name: str
) -> tuple[list[datetime], list[float], list[bool]]:
    xs: list[datetime] = []
    ys: list[float] = []
    obs: list[bool] = []
    for sample in samples:
        match = [
            r
            for r in rows_for_sample(sky, sample["i"])
            if r["kind"] == kind and r["name"] == name
        ]
        if not match:
            continue
        xs.append(_local_time(sample["time"]))
        ys.append(float(match[0]["alt_deg"]))
        obs.append(bool(match[0].get("obscured")))
    return xs, ys, obs


def _altitude_series(
    samples: list[dict[str, Any]], sky: list[dict[str, Any]], series: str
) -> list[tuple[str, str, list[datetime], list[float], list[bool]]]:
    out: list[tuple[str, str, list[datetime], list[float], list[bool]]] = []
    for kind, name in _altitude_targets(series, samples, sky):
        xs, ys, obs = _body_altitude(samples, sky, kind, name)
        if not xs or max(ys) < 0:
            continue
        out.append((kind, name, xs, ys, obs))
    return out


def plot_altitude(
    path: Path,
    night_id: int,
    kind: str,
    name: str,
    xs: list[datetime],
    ys: list[float],
    obs: list[bool],
    span: list[datetime],
) -> Path:
    fig, ax = plt.subplots(figsize=(10.0, 4.4), facecolor=PAPER)
    color = _series_color(kind, name)
    ax.plot(xs, ys, color=color, lw=1.8)
    hidden_x = [x for x, o, y in zip(xs, obs, ys, strict=True) if o or y < 0]
    hidden_y = [y for o, y in zip(obs, ys, strict=True) if o or y < 0]
    if hidden_x:
        ax.scatter(hidden_x, hidden_y, s=16, c=color, alpha=0.25, zorder=2)
    ax.axhline(0.0, color=MUTED, lw=0.8, ls="--")
    ax.set_ylim(-15, 90)
    _clock_axis(ax, span)
    ax.set_ylabel("altitude °")
    _style_axes(ax, f"Night {night_id} · {name}")
    return _savefig(fig, path)


def plot_ahead(
    path: Path,
    sample: dict[str, Any],
    rows: list[dict[str, Any]],
    dem_array: np.ndarray | None,
    dem_transform: Any,
    guide: dict[str, Any] | None = None,
) -> Path:
    fig, ax = plt.subplots(figsize=(10, 4.6), facecolor=PAPER)
    heading = float(sample.get("heading_deg") or 0.0)
    rels = np.linspace(-AHEAD_HALF_DEG, AHEAD_HALF_DEG, 181)
    if dem_array is not None and dem_transform is not None:
        horizon = horizon_along_azs(
            dem_array,
            dem_transform,
            float(sample["lon"]),
            float(sample["lat"]),
            float(sample["elev_m"]),
            heading + rels,
            max_km=15.0,
            step_m=100.0,
        )
        ax.fill_between(rels, horizon, -8.0, color=HORIZON_FILL, zorder=1)
        ax.plot(rels, horizon, color=HORIZON_LINE, lw=1.2, zorder=2)
    ax.axvline(0.0, color=RUN, lw=0.9, ls="--", zorder=3, alpha=0.75)
    ax.text(0.0, 84, "ahead", color=RUN, ha="center", va="bottom", fontsize=8)
    guide_name = guide["name"] if guide else None
    for row in rows:
        alt = float(row["alt_deg"])
        rel = rel_bearing_deg(row["az_deg"], heading)
        if alt < -5 or abs(rel) > AHEAD_HALF_DEG:
            continue
        kind = row["kind"]
        name = row["name"]
        obscured = bool(row.get("obscured"))
        if kind == "planet":
            color = PLANET_COLORS.get(name, INK)
            ax.scatter(
                rel, alt, s=80, c=color, zorder=5, alpha=0.35 if obscured else 1.0, edgecolors=color
            )
            if not obscured:
                _annotate(ax, name, (rel, alt), color=color)
        elif kind == "moon":
            ax.scatter(rel, alt, s=120, c=MOON, edgecolors=INK, zorder=5)
            _annotate(ax, "Moon", (rel, alt), color=MOON)
        elif kind == "feature":
            ax.scatter(rel, alt, s=60, marker="*", c=MW, zorder=5)
            _annotate(ax, "MW", (rel, alt), color=MW)
        elif kind == "star" and name in NAV_STARS and alt >= 5:
            mag = float(row["mag"]) if row.get("mag") is not None else 2.0
            size = max(12.0, 52.0 * 0.65**mag)
            color = star_color(name)
            is_guide = name == guide_name
            ax.scatter(rel, alt, s=size * (1.6 if is_guide else 1.0), c=color, zorder=4)
            label = f"{name} · ahead" if is_guide else name
            _annotate(ax, label, (rel, alt), color=GUIDE if is_guide else color)
    ax.set_xlim(-AHEAD_HALF_DEG, AHEAD_HALF_DEG)
    ax.set_xticks([-90, -45, 0, 45, 90])
    ax.set_xticklabels(["90° L", "45° L", "ahead", "45° R", "90° R"])
    ax.set_ylim(-8, 90)
    ax.set_ylabel("altitude °")
    title = (
        f"{fmt_time(sample['time'])}  ·  km {sample['dist_km']:.1f}  ·  "
        f"{fmt_hours(sample['elapsed_h'])}  ·  looking along the course"
    )
    _style_axes(ax, title)
    return _savefig(fig, path)


def write_plots(
    out_dir: Path,
    lons: np.ndarray,
    lats: np.ndarray,
    eles: np.ndarray,
    nights: dict[str, Any],
    samples: list[dict[str, Any]],
    sky: list[dict[str, Any]],
    dem_array: np.ndarray | None = None,
    dem_transform: Any = None,
    spots_cfg: dict[str, Any] | None = None,
) -> list[Path]:
    plots_dir = out_dir / "plots"
    slon, slat, dist, sele = sample_along(lons, lats, 200.0, eles)
    if dem_array is not None and dem_transform is not None:
        from dem import sample_elev_xy

        elev = np.array(
            [
                sample_elev_xy(dem_array, dem_transform, float(lon), float(lat), None)
                for lon, lat in zip(slon, slat, strict=True)
            ],
            dtype=float,
        )
        missing = ~np.isfinite(elev)
        if np.any(missing):
            elev[missing] = sele[missing]
    else:
        elev = sele
    profiles = _horizon_profiles(samples, dem_array, dem_transform)
    scores = score_samples(samples, sky, profiles)
    guides = {
        int(sample["i"]): guide_star(sample, rows_for_sample(sky, sample["i"]))
        for sample in samples
    }
    knobs = spots_cfg or {}
    picked = pick_best_spots(
        scores,
        min_gap_km=float(knobs.get("min_gap_km", SPOT_GAP_KM)),
        max_per_night=int(knobs.get("max_per_night", SPOT_MAX_PER_NIGHT)),
        score_floor=float(knobs.get("score_floor", SPOT_SCORE_FLOOR)),
    )
    picked_ids = {int(s["i"]) for s in picked}
    written: list[Path] = [
        plot_course(
            plots_dir / "course.png",
            slon,
            slat,
            dist,
            nights,
            samples,
            dem_array,
            dem_transform,
            featured=picked,
        ),
        plot_profile(plots_dir / "profile.png", dist, elev, nights, samples, featured=picked),
        plot_spots(
            plots_dir / "spots.png",
            slon,
            slat,
            dist,
            elev,
            nights,
            scores,
            dem_array,
            dem_transform,
        ),
    ]
    by_night: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        by_night[int(sample["night_id"])].append(sample)
    for nid, group in by_night.items():
        span = [_local_time(s["time"]) for s in group]
        for series in ("planets", "stars"):
            for kind, name, xs, ys, obs in _altitude_series(group, sky, series):
                stem = altitude_stem(nid, kind, name)
                written.append(
                    plot_altitude(
                        plots_dir / f"{stem}.png", nid, kind, name, xs, ys, obs, span
                    )
                )
        for sample in group:
            if int(sample["i"]) not in picked_ids:
                continue
            stem = sample_stem(sample)
            rows = rows_for_sample(sky, sample["i"])
            guide = guides.get(int(sample["i"]))
            profile = profiles.get(int(sample["i"]))
            written.append(
                plot_sky_disc(plots_dir / f"{stem}.png", sample, rows, profile, guide)
            )
            written.append(
                plot_ahead(
                    plots_dir / f"{stem}-ahead.png",
                    sample,
                    rows,
                    dem_array,
                    dem_transform,
                    guide,
                )
            )
            written.append(
                plot_course(
                    plots_dir / f"{stem}-course.png",
                    slon,
                    slat,
                    dist,
                    nights,
                    samples,
                    dem_array,
                    dem_transform,
                    featured=picked,
                    highlight_i=int(sample["i"]),
                )
            )
    dump_json(out_dir / "spots.json", picked)
    write_spots_gpx(out_dir / "stargazing-spots.gpx", picked)
    kept = {path.name for path in written}
    if plots_dir.is_dir():
        for old in plots_dir.glob("*.png"):
            if old.name not in kept:
                old.unlink()
    return written


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Course, sky-disc, altitude, spots, and look-ahead plots."
    )
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--site-dir", type=Path, default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    datadir = data_dir(args.data_dir)
    site_dir = (args.site_dir or REPO_ROOT / "docs").expanduser()
    lons, lats, eles, _name = read_track(datadir / "input.gpx")
    dem_path = datadir / "dem" / "glo30.tif"
    dem_array = None
    dem_transform = None
    if dem_path.is_file():
        dem_array, dem_transform, _ = load_dem_array(dem_path)
    spots_cfg = cfg.get("spots")
    written = write_plots(
        site_dir,
        lons,
        lats,
        eles,
        load_json(datadir / "nights.json"),
        load_json(datadir / "samples.json"),
        load_json(datadir / "sky.json"),
        dem_array,
        dem_transform,
        spots_cfg=spots_cfg if isinstance(spots_cfg, dict) else None,
    )
    print(f"{len(written)} plots → {site_dir / 'plots'}")


if __name__ == "__main__":
    main()
