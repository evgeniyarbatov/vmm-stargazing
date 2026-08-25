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

NIGHT_COLORS = {1: "#89b4fa", 2: "#cba6f7", 3: "#a6e3a1"}
PLANET_COLORS = {
    "Mercury": "#a6adc8",
    "Venus": "#f9e2af",
    "Mars": "#f38ba8",
    "Jupiter": "#fab387",
    "Saturn": "#94e2d5",
}
SKY_BG = "#0b1020"
DAY_TRACK = "#6c7086"
ALT_STARS = {"Vega", "Altair", "Deneb", "Sirius", "Betelgeuse", "Antares"}


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
    fig.savefig(path, dpi=140, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


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
    fig, ax = plt.subplots(figsize=(8.5, 8.5), facecolor="#1e1e2e")
    ax.set_facecolor("#1e1e2e")
    if dem_array is not None and dem_transform is not None:
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
    ax.plot(lons, lats, color=DAY_TRACK, lw=1.0, zorder=2, label="day")
    night_list = list(nights.get("nights") or [])
    for night in night_list:
        nid = int(night["night_id"])
        mask = (dist >= float(night["dist0_km"]) * 1000.0) & (dist <= float(night["dist1_km"]) * 1000.0)
        ax.plot(
            lons[mask],
            lats[mask],
            color=NIGHT_COLORS.get(nid, "#f5c2e7"),
            lw=2.2,
            zorder=3,
            label=f"night {nid}",
        )
    labeled = _edge_samples(samples)
    labeled_ids = {s["i"] for s in labeled}
    for sample in samples:
        color = NIGHT_COLORS.get(int(sample["night_id"]), "#f5c2e7")
        ax.scatter(
            sample["lon"],
            sample["lat"],
            s=22 if sample["i"] in labeled_ids else 10,
            c=color,
            edgecolors="white",
            linewidths=0.4,
            zorder=4,
        )
        if sample["i"] in labeled_ids:
            ax.annotate(
                f"{sample['dist_km']:.0f} km\n{fmt_time(sample['time'])}",
                (sample["lon"], sample["lat"]),
                textcoords="offset points",
                xytext=(6, 6),
                fontsize=7,
                color="white",
                zorder=5,
            )
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("lon")
    ax.set_ylabel("lat")
    ax.tick_params(colors="#cdd6f4")
    ax.xaxis.label.set_color("#cdd6f4")
    ax.yaxis.label.set_color("#cdd6f4")
    for spine in ax.spines.values():
        spine.set_color("#45475a")
    ax.legend(loc="upper right", fontsize=8, framealpha=0.7)
    ax.set_title("Night samples on course (cutoff pace)", color="#cdd6f4")
    return _savefig(fig, path)


def plot_profile(
    path: Path,
    dist: np.ndarray,
    elev: np.ndarray,
    nights: dict[str, Any],
    samples: list[dict[str, Any]],
) -> Path:
    fig, ax = plt.subplots(figsize=(10, 3.8), facecolor="#1e1e2e")
    ax.set_facecolor("#1e1e2e")
    km = dist / 1000.0
    ax.plot(km, elev, color="#cdd6f4", lw=1.1)
    for night in nights.get("nights") or []:
        nid = int(night["night_id"])
        ax.axvspan(
            float(night["dist0_km"]),
            float(night["dist1_km"]),
            color=NIGHT_COLORS.get(nid, "#f5c2e7"),
            alpha=0.25,
            label=f"night {nid}",
        )
    for sample in _edge_samples(samples):
        ax.scatter(sample["dist_km"], sample["elev_m"], c="white", s=18, zorder=3)
        ax.annotate(
            fmt_time(sample["time"]),
            (sample["dist_km"], sample["elev_m"]),
            textcoords="offset points",
            xytext=(4, 6),
            fontsize=7,
            color="white",
        )
    ax.set_xlabel("km")
    ax.set_ylabel("elev m")
    ax.set_title("Elevation · shaded = astronomical night at cutoff pace", color="#cdd6f4")
    ax.tick_params(colors="#cdd6f4")
    ax.xaxis.label.set_color("#cdd6f4")
    ax.yaxis.label.set_color("#cdd6f4")
    for spine in ax.spines.values():
        spine.set_color("#45475a")
    ax.legend(loc="upper right", fontsize=8, framealpha=0.7)
    ax.set_xlim(float(km[0]), float(km[-1]))
    return _savefig(fig, path)


def plot_sky_disc(
    path: Path,
    sample: dict[str, Any],
    rows: list[dict[str, Any]],
    profile: np.ndarray | None,
) -> Path:
    fig = plt.figure(figsize=(7.2, 7.6), facecolor=SKY_BG)
    ax = fig.add_subplot(111, projection="polar")
    ax.set_facecolor(SKY_BG)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 90)
    ax.set_yticks([30, 60, 90])
    ax.set_yticklabels(["60°", "30°", "horizon"], color="#6c7086", fontsize=8)
    ax.set_xticks(np.radians([0, 90, 180, 270]))
    ax.set_xticklabels(["N", "E", "S", "W"], color="#cdd6f4")
    ax.grid(color="#313244", lw=0.6)
    ax.spines["polar"].set_color("#45475a")

    if profile is not None:
        az = np.linspace(0.0, 360.0, 361)
        r_h = np.clip([90.0 - horizon_at_az(profile, a) for a in az], 0.0, 90.0)
        theta = np.radians(az)
        ax.fill_between(theta, r_h, 90.0, color="#11111b", alpha=0.95, zorder=1)
        ax.plot(theta, r_h, color="#6c7086", lw=0.9, zorder=2)

    heading = float(sample.get("heading_deg") or 0.0)
    ax.annotate(
        "",
        xy=(np.radians(heading), 88),
        xytext=(np.radians(heading), 72),
        arrowprops={"arrowstyle": "->", "color": "#f5c2e7", "lw": 1.6},
        zorder=6,
    )
    ax.text(np.radians(heading), 62, "run", color="#f5c2e7", ha="center", va="center", fontsize=8)

    for row in rows:
        alt = float(row["alt_deg"])
        if alt < 0:
            continue
        r, theta = altaz_to_rtheta(alt, float(row["az_deg"]))
        kind = row["kind"]
        obscured = bool(row.get("obscured"))
        name = row["name"]
        if kind == "planet":
            color = PLANET_COLORS.get(name, "#cdd6f4")
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
            ax.annotate(name, (theta, r), textcoords="offset points", xytext=(5, 5), color=color, fontsize=8)
        elif kind == "moon":
            ax.scatter(theta, r, s=160, c="#f5e0dc", edgecolors="#bac2de", zorder=5)
            ax.annotate("Moon", (theta, r), textcoords="offset points", xytext=(6, 6), color="#f5e0dc", fontsize=8)
        elif kind == "feature":
            ax.scatter(theta, r, s=70, marker="*", c="#cba6f7", zorder=5)
            ax.annotate("MW", (theta, r), textcoords="offset points", xytext=(5, 5), color="#cba6f7", fontsize=8)
        elif kind == "star" and name in NAV_STARS and alt >= 5:
            mag = float(row["mag"]) if row.get("mag") is not None else 2.0
            size = max(8.0, 55.0 * 0.65**mag)
            ax.scatter(theta, r, s=size, c="white", zorder=4, alpha=0.3 if obscured else 0.95)
            if mag <= 1.3 and not obscured:
                ax.annotate(name, (theta, r), textcoords="offset points", xytext=(4, 4), color="#bac2de", fontsize=7)

    title = (
        f"{fmt_time(sample['time'])}  ·  km {sample['dist_km']:.1f}  ·  "
        f"{fmt_hours(sample['elapsed_h'])}"
    )
    ax.set_title(title, color="#cdd6f4", pad=12, fontsize=10)
    fig.text(0.5, 0.02, "zenith centre · north up · filled edge = terrain horizon", ha="center", color="#6c7086", fontsize=8)
    return _savefig(fig, path)


def plot_altitude(
    path: Path,
    night_id: int,
    samples: list[dict[str, Any]],
    sky: list[dict[str, Any]],
) -> Path:
    fig, ax = plt.subplots(figsize=(10, 4.4), facecolor="#1e1e2e")
    ax.set_facecolor("#1e1e2e")
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
        color = PLANET_COLORS.get(name, "#cdd6f4" if kind != "moon" else "#f5e0dc")
        if kind == "star":
            color = "#bac2de"
        ax.plot(xs, ys, color=color, lw=1.6 if kind != "star" else 0.9, label=name)
        hidden_x = [x for x, o, y in zip(xs, obs, ys, strict=True) if o or y < 0]
        hidden_y = [y for o, y in zip(obs, ys, strict=True) if o or y < 0]
        if hidden_x:
            ax.scatter(hidden_x, hidden_y, s=12, c=color, alpha=0.25, zorder=2)

    ax.axhline(0.0, color="#6c7086", lw=0.8, ls="--")
    ax.set_ylim(-15, 90)
    if hours:
        ax.set_xlim(min(hours), max(hours))
    ax.set_xlabel("elapsed h")
    ax.set_ylabel("altitude °")
    ax.set_title(f"Night {night_id} · altitude (dashed 0° = geometric horizon)", color="#cdd6f4")
    ax.tick_params(colors="#cdd6f4")
    ax.xaxis.label.set_color("#cdd6f4")
    ax.yaxis.label.set_color("#cdd6f4")
    for spine in ax.spines.values():
        spine.set_color("#45475a")
    ax.legend(loc="upper left", fontsize=7, ncol=3, framealpha=0.7)
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
    written: list[Path] = [
        plot_course(plots_dir / "course.png", slon, slat, dist, nights, samples, dem_array, dem_transform),
        plot_profile(plots_dir / "profile.png", dist, elev, nights, samples),
    ]
    by_night: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        by_night[int(sample["night_id"])].append(sample)
    keys = key_samples(samples)
    for nid, group in by_night.items():
        written.append(plot_altitude(plots_dir / f"night{nid}-alt.png", nid, group, sky))
        for sample in keys:
            if int(sample["night_id"]) != nid:
                continue
            profile = None
            if dem_array is not None and dem_transform is not None:
                profile = horizon_profile(
                    dem_array,
                    dem_transform,
                    float(sample["lon"]),
                    float(sample["lat"]),
                    float(sample["elev_m"]),
                    n_az=36,
                    max_km=15.0,
                    step_m=200.0,
                )
            stem = disc_stem(sample, group)
            written.append(
                plot_sky_disc(
                    plots_dir / f"{stem}.png",
                    sample,
                    rows_for_sample(sky, sample["i"]),
                    profile,
                )
            )
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Course, sky-disc, and altitude plots.")
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
