from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np
from catalog import NAV_STARS
from config import data_dir, load_config
from horizon import horizon_at_az, horizon_profile, load_dem_array
from report import disc_stem, fmt_hours, fmt_time, key_samples, rows_for_sample
from utils import ensure_parent, load_json, sample_along

from gpx import read_track

PAPER = "#ffffff"
INK = "#1e1e2e"
MUTED = "#6c6f85"
GRID = "#ccd0da"
SPINE = "#bcc0cc"
HORIZON_FILL = "#e6e9ef"
HORIZON_LINE = "#8c8fa1"
DAY_TRACK = "#6c6f85"
RUN = "#d20f39"
GUIDE = "#df8e1d"
MOON = "#dc8a78"
MW = "#8839ef"
STAR = "#1e1e2e"
AHEAD_DEG = 20.0
OPEN_REF_DEG = 45.0
NIGHT_COLORS = {1: "#1e66f5", 2: "#8839ef", 3: "#40a02b"}
PLANET_COLORS = {
    "Mercury": "#7c7f93",
    "Venus": "#df8e1d",
    "Mars": "#d20f39",
    "Jupiter": "#fe640b",
    "Saturn": "#179299",
}
ALT_STARS = {"Vega", "Altair", "Deneb", "Sirius", "Betelgeuse", "Antares"}
STEER_PALETTE = (
    "#1e66f5",
    "#d20f39",
    "#40a02b",
    "#df8e1d",
    "#8839ef",
    "#fe640b",
    "#179299",
    "#dd7878",
    "#04a5e5",
    "#e64553",
    "#7287fd",
    "#4a7c2c",
    "#ea76cb",
    "#9d6b3a",
    "#00a86b",
    "#1a1a1a",
    "#6c2c6f",
    "#c6a645",
)


def altaz_to_rtheta(alt_deg: float, az_deg: float) -> tuple[float, float]:
    return 90.0 - float(alt_deg), np.radians(float(az_deg) % 360.0)


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


def _mean_horizon(profile: np.ndarray | None, rows: list[dict[str, Any]]) -> float:
    if profile is not None and len(profile) > 0:
        return float(np.mean(profile))
    vals = [float(r["horizon_deg"]) for r in rows if r.get("horizon_deg") is not None]
    return float(np.mean(vals)) if vals else 0.0


def score_sample(
    sample: dict[str, Any],
    rows: list[dict[str, Any]],
    profile: np.ndarray | None,
    elev_min: float,
    elev_max: float,
) -> dict[str, Any]:
    open_sky = 1.0 - min(max(_mean_horizon(profile, rows) / OPEN_REF_DEG, 0.0), 1.0)
    span = max(elev_max - elev_min, 1.0)
    elev_score = (float(sample["elev_m"]) - elev_min) / span
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
        "elev_score": elev_score,
        "moon_penalty": moon_penalty,
        "mw_bonus": float(mw_up),
    }


def _star_color(name: str) -> str:
    names = sorted(NAV_STARS)
    if name not in names:
        return STAR
    return STEER_PALETTE[names.index(name) % len(STEER_PALETTE)]


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


def _break_jumps(
    xs: list[float], ys: list[float], limit: float = 120.0
) -> tuple[list[float], list[float]]:
    if not xs:
        return [], []
    ox = [xs[0]]
    oy = [ys[0]]
    for x, y, prev_y in zip(xs[1:], ys[1:], ys[:-1], strict=True):
        if abs(y - prev_y) > limit:
            ox.append(x)
            oy.append(float("nan"))
        ox.append(x)
        oy.append(y)
    return ox, oy


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


def _zoom_to_samples(ax: Any, samples: list[dict[str, Any]], pad_frac: float = 0.4) -> None:
    xs = [float(s["lon"]) for s in samples]
    ys = [float(s["lat"]) for s in samples]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    pad_x = max((x1 - x0) * pad_frac, 0.012)
    pad_y = max((y1 - y0) * pad_frac, 0.012)
    ax.set_xlim(x0 - pad_x, x1 + pad_x)
    ax.set_ylim(y0 - pad_y, y1 + pad_y)


def _guide_label_ids(
    group: list[dict[str, Any]],
    guides: dict[int, dict[str, Any] | None],
    min_deg: float = 0.015,
) -> set[int]:
    picked: list[dict[str, Any]] = []
    n = len(group)
    for idx, sample in enumerate(group):
        guide = guides.get(int(sample["i"]))
        is_end = idx == 0 or idx == n - 1
        rel = abs(float(guide["rel_deg"])) if guide else 999.0
        in_cone = rel <= AHEAD_DEG
        if not (is_end or in_cone):
            continue
        if picked:
            prev = picked[-1]
            close = (
                abs(float(sample["lon"]) - float(prev["lon"])) < min_deg
                and abs(float(sample["lat"]) - float(prev["lat"])) < min_deg
            )
            if close and (not is_end or rel > AHEAD_DEG):
                continue
        picked.append(sample)
    return {int(s["i"]) for s in picked}


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
            n_az=36,
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
) -> Path:
    fig, ax = plt.subplots(figsize=(8.5, 8.5), facecolor=PAPER)
    if dem_array is not None and dem_transform is not None:
        _draw_hillshade(ax, dem_array, dem_transform)
    _draw_course_track(ax, lons, lats, dist, nights)
    labeled = _edge_samples(samples)
    labeled_ids = {s["i"] for s in labeled}
    for sample in samples:
        color = NIGHT_COLORS.get(int(sample["night_id"]), "#ea76cb")
        ax.scatter(
            sample["lon"],
            sample["lat"],
            s=22 if sample["i"] in labeled_ids else 10,
            c=color,
            edgecolors=INK,
            linewidths=0.4,
            zorder=4,
        )
        if sample["i"] in labeled_ids:
            _annotate(
                ax,
                f"{sample['dist_km']:.0f} km\n{fmt_time(sample['time'])}",
                (sample["lon"], sample["lat"]),
            )
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("lon")
    ax.set_ylabel("lat")
    _style_axes(ax, "Night samples on course (cutoff pace)")
    _legend(ax, loc="upper right")
    return _savefig(fig, path)


def plot_profile(
    path: Path,
    dist: np.ndarray,
    elev: np.ndarray,
    nights: dict[str, Any],
    samples: list[dict[str, Any]],
) -> Path:
    fig, ax = plt.subplots(figsize=(10, 3.8), facecolor=PAPER)
    km = dist / 1000.0
    ax.plot(km, elev, color=INK, lw=1.1)
    _night_spans(ax, nights)
    for sample in _edge_samples(samples):
        ax.scatter(sample["dist_km"], sample["elev_m"], c=INK, s=18, zorder=3)
        _annotate(
            ax, fmt_time(sample["time"]), (sample["dist_km"], sample["elev_m"]), xytext=(4, 6)
        )
    ax.set_xlabel("km")
    ax.set_ylabel("elev m")
    _style_axes(ax, "Elevation · shaded = astronomical night at cutoff pace")
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
    by_night: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in scores:
        by_night[int(row["night_id"])].append(row)
    labeled: list[dict[str, Any]] = []
    for nid in sorted(by_night):
        ranked = sorted(by_night[nid], key=lambda row: row["score"], reverse=True)
        labeled.extend(ranked[:1])
    for row in labeled:
        _annotate(
            ax_map,
            f"{row['dist_km']:.0f} km · {row['score']:.2f}",
            (row["lon"], row["lat"]),
        )
    ax_map.set_aspect("equal", adjustable="box")
    ax_map.set_xlabel("lon")
    ax_map.set_ylabel("lat")
    _style_axes(ax_map, "Stargazing spots (cutoff-pace night samples)")
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


def plot_steer_map(
    path: Path,
    lons: np.ndarray,
    lats: np.ndarray,
    dist: np.ndarray,
    nights: dict[str, Any],
    samples: list[dict[str, Any]],
    guides: dict[int, dict[str, Any] | None],
    dem_array: np.ndarray | None,
    dem_transform: Any,
) -> Path:
    by_night: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        by_night[int(sample["night_id"])].append(sample)
    night_ids = sorted(by_night) or [1]
    n = len(night_ids)
    fig, axes = plt.subplots(n, 1, figsize=(8.5, 5.2 * n), facecolor=PAPER)
    if n == 1:
        axes = [axes]
    for ax, nid in zip(axes, night_ids, strict=True):
        group = by_night[nid]
        if dem_array is not None and dem_transform is not None:
            _draw_hillshade(ax, dem_array, dem_transform)
        _draw_course_track(ax, lons, lats, dist, nights)
        labeled_ids = _guide_label_ids(group, guides)
        for sample in group:
            gid = int(sample["i"])
            guide = guides.get(gid)
            ax.scatter(
                sample["lon"],
                sample["lat"],
                s=22 if gid in labeled_ids else 10,
                c=GUIDE if guide else MUTED,
                edgecolors=INK,
                linewidths=0.4,
                zorder=4,
            )
        for j, sample in enumerate(s for s in group if int(s["i"]) in labeled_ids):
            _annotate(
                ax,
                guide_label(guides.get(int(sample["i"]))),
                (sample["lon"], sample["lat"]),
                xytext=(6, 6) if j % 2 == 0 else (6, -14),
            )
        ax.set_xlabel("lon")
        ax.set_ylabel("lat")
        _style_axes(ax, f"Night {nid} · guide star")
        _zoom_to_samples(ax, group)
        ax.set_aspect("equal", adjustable="box")
        _legend(ax, loc="upper right")
    fig.suptitle("Guide star along the course (brightest near heading)", color=INK)
    fig.tight_layout()
    return _savefig(fig, path)


def plot_steer(
    path: Path,
    night_id: int,
    samples: list[dict[str, Any]],
    sky: list[dict[str, Any]],
) -> Path:
    fig, ax = plt.subplots(figsize=(10, 4.6), facecolor=PAPER)
    ax.axhspan(-AHEAD_DEG, AHEAD_DEG, color=GUIDE, alpha=0.22, zorder=0, label="ahead ±20°")
    ax.axhline(0.0, color=INK, lw=0.8, zorder=1)
    names = sorted(
        {
            r["name"]
            for r in sky
            if r["kind"] == "star"
            and r["name"] in NAV_STARS
            and r["sample_i"] in {s["i"] for s in samples}
        }
    )
    plotted = 0
    for name in names:
        xs: list[float] = []
        ys: list[float] = []
        for sample in samples:
            match = [
                r
                for r in rows_for_sample(sky, sample["i"])
                if r["kind"] == "star" and r["name"] == name
            ]
            if not match:
                continue
            row = match[0]
            if float(row["alt_deg"]) < 5.0 or row.get("obscured"):
                continue
            xs.append(float(sample["dist_km"]))
            ys.append(rel_bearing_deg(row["az_deg"], sample["heading_deg"]))
        if not xs:
            continue
        if min(abs(y) for y in ys) > 30.0:
            continue
        color = _star_color(name)
        if len(xs) == 1:
            ax.scatter(xs, ys, s=18, c=color, zorder=3, label=name)
        else:
            bx, by = _break_jumps(xs, ys)
            ax.plot(bx, by, color=color, lw=1.4, zorder=3, label=name)
        plotted += 1
    if samples:
        ax.set_xlim(float(samples[0]["dist_km"]), float(samples[-1]["dist_km"]))
    ax.set_ylim(-180, 180)
    ax.set_yticks([-180, -90, 0, 90, 180])
    ax.set_yticklabels(["behind", "left", "ahead", "right", "behind"])
    ax.set_xlabel("km")
    ax.set_ylabel("bearing vs heading")
    _style_axes(ax, f"Night {night_id} · steer by stars (0° = trail heading)")
    if plotted:
        _legend(ax, loc="upper right", fontsize=7, ncol=3)
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
            ax.scatter(
                theta,
                r,
                s=size * (1.6 if is_guide else 1.0),
                c=GUIDE if is_guide else STAR,
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
                label = f"{name} · steer" if is_guide else name
                ax.annotate(
                    label,
                    (theta, r),
                    textcoords="offset points",
                    xytext=(4, 4),
                    color=GUIDE if is_guide else MUTED,
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
        "zenith centre · north up · filled edge = terrain horizon · gold = guide star",
        ha="center",
        color=MUTED,
        fontsize=8,
    )
    return _savefig(fig, path)


def plot_altitude(
    path: Path,
    night_id: int,
    samples: list[dict[str, Any]],
    sky: list[dict[str, Any]],
) -> Path:
    fig, ax = plt.subplots(figsize=(10, 4.4), facecolor=PAPER)
    names: list[tuple[str, str]] = [("planet", n) for n in PLANET_COLORS] + [("moon", "Moon")]
    up_nav = {
        r["name"]
        for r in sky
        if r["kind"] == "star" and r["name"] in ALT_STARS and float(r["alt_deg"]) > 10
    }
    for name in sorted(up_nav):
        names.append(("star", name))

    hours = [float(s["elapsed_h"]) for s in samples]
    for kind, name in names:
        xs: list[float] = []
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
            xs.append(float(sample["elapsed_h"]))
            ys.append(float(match[0]["alt_deg"]))
            obs.append(bool(match[0].get("obscured")))
        if not xs or max(ys) < 0:
            continue
        color = PLANET_COLORS.get(name, STAR if kind != "moon" else MOON)
        if kind == "star":
            color = MUTED
        ax.plot(xs, ys, color=color, lw=1.6 if kind != "star" else 0.9, label=name)
        hidden_x = [x for x, o, y in zip(xs, obs, ys, strict=True) if o or y < 0]
        hidden_y = [y for o, y in zip(obs, ys, strict=True) if o or y < 0]
        if hidden_x:
            ax.scatter(hidden_x, hidden_y, s=12, c=color, alpha=0.25, zorder=2)

    ax.axhline(0.0, color=MUTED, lw=0.8, ls="--")
    ax.set_ylim(-15, 90)
    if hours:
        ax.set_xlim(min(hours), max(hours))
    ax.set_xlabel("elapsed h")
    ax.set_ylabel("altitude °")
    _style_axes(ax, f"Night {night_id} · altitude (dashed 0° = geometric horizon)")
    _legend(ax, loc="upper left", fontsize=7, ncol=3)
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
    elevs = [float(s["elev_m"]) for s in samples]
    elev_min = min(elevs) if elevs else 0.0
    elev_max = max(elevs) if elevs else 1.0
    scores = [
        score_sample(
            sample,
            rows_for_sample(sky, sample["i"]),
            profiles.get(int(sample["i"])),
            elev_min,
            elev_max,
        )
        for sample in samples
    ]
    guides = {
        int(sample["i"]): guide_star(sample, rows_for_sample(sky, sample["i"]))
        for sample in samples
    }
    written: list[Path] = [
        plot_course(
            plots_dir / "course.png", slon, slat, dist, nights, samples, dem_array, dem_transform
        ),
        plot_profile(plots_dir / "profile.png", dist, elev, nights, samples),
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
        plot_steer_map(
            plots_dir / "steer.png",
            slon,
            slat,
            dist,
            nights,
            samples,
            guides,
            dem_array,
            dem_transform,
        ),
    ]
    by_night: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        by_night[int(sample["night_id"])].append(sample)
    keys = key_samples(samples)
    for nid, group in by_night.items():
        written.append(plot_altitude(plots_dir / f"night{nid}-alt.png", nid, group, sky))
        written.append(plot_steer(plots_dir / f"night{nid}-steer.png", nid, group, sky))
        for sample in keys:
            if int(sample["night_id"]) != nid:
                continue
            stem = disc_stem(sample, group)
            written.append(
                plot_sky_disc(
                    plots_dir / f"{stem}.png",
                    sample,
                    rows_for_sample(sky, sample["i"]),
                    profiles.get(int(sample["i"])),
                    guides.get(int(sample["i"])),
                )
            )
    return written


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Course, sky-disc, altitude, spots, and steer plots."
    )
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args()
    load_config(args.config)
    datadir = data_dir(args.data_dir)
    lons, lats, eles, _name = read_track(datadir / "input.gpx")
    dem_path = datadir / "dem" / "glo30.tif"
    dem_array = None
    dem_transform = None
    if dem_path.is_file():
        dem_array, dem_transform, _ = load_dem_array(dem_path)
    written = write_plots(
        datadir / "out",
        lons,
        lats,
        eles,
        load_json(datadir / "nights.json"),
        load_json(datadir / "samples.json"),
        load_json(datadir / "sky.json"),
        dem_array,
        dem_transform,
    )
    print(f"{len(written)} plots → {datadir / 'out' / 'plots'}")


if __name__ == "__main__":
    main()
