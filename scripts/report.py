from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from catalog import NAV_STARS
from config import data_dir, load_config
from utils import DEM_LIMITS_NOTE, compass8, ensure_parent, load_json


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def fmt_time(value: str | datetime) -> str:
    dt = parse_dt(value) if isinstance(value, str) else value
    try:
        return dt.strftime("%a %-d %b %H:%M")
    except ValueError:
        return dt.strftime("%a %d %b %H:%M")


def fmt_hours(hours: float) -> str:
    total = int(round(hours * 60))
    h, m = divmod(total, 60)
    return f"{h}h {m:02d}m"


def fmt_altaz(alt: float, az: float) -> str:
    return f"{alt:.0f}° {compass8(az)} ({az:.0f}°)"


def rows_for_sample(sky: list[dict[str, Any]], sample_i: int) -> list[dict[str, Any]]:
    return [r for r in sky if r["sample_i"] == sample_i]


def visible(row: dict[str, Any], min_alt: float = 0.0) -> bool:
    return float(row["alt_deg"]) >= min_alt and not row.get("obscured")


def disc_stem(sample: dict[str, Any], group: list[dict[str, Any]]) -> str:
    nid = int(sample["night_id"])
    if sample["i"] == group[0]["i"]:
        return f"night{nid}-dusk"
    if sample["i"] == group[-1]["i"]:
        return f"night{nid}-dawn"
    return f"night{nid}-midnight"


def key_samples(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_night: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for s in samples:
        by_night[int(s["night_id"])].append(s)
    out: list[dict[str, Any]] = []
    for night_id in sorted(by_night):
        group = by_night[night_id]
        if len(group) <= 3:
            out.extend(group)
            continue
        mid = min(group, key=midnightish)
        seen: set[int] = set()
        for p in (group[0], mid, group[-1]):
            if p["i"] not in seen:
                out.append(p)
                seen.add(p["i"])
    return out


def midnightish(sample: dict[str, Any]) -> float:
    hour = parse_dt(sample["time"]).hour + parse_dt(sample["time"]).minute / 60.0
    return min(abs(hour - 0), abs(hour - 24))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def planet_lines(rows: list[dict[str, Any]]) -> list[str]:
    planets = [r for r in rows if r["kind"] == "planet" and float(r["alt_deg"]) >= 0]
    lines = []
    for r in planets:
        mag = f", mag {r['mag']:.1f}" if r.get("mag") is not None else ""
        extra = " — behind terrain" if r.get("obscured") else ""
        lines.append(f"- **{r['name']}**: {fmt_altaz(r['alt_deg'], r['az_deg'])}{mag}{extra}")
    return lines


def constellation_groups(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    visible_stars = [r for r in rows if r["kind"] == "star" and visible(r)]
    by_tag: dict[str, list[str]] = {"overhead": [], "rising": [], "setting": [], "up": []}
    seen: dict[str, str] = {}
    for r in visible_stars:
        name = r.get("constellation") or r["name"]
        tag = r["tag"] if r["tag"] in by_tag else "up"
        prev = seen.get(name)
        if prev is None:
            seen[name] = tag
            continue
        rank = {"overhead": 0, "up": 1, "rising": 2, "setting": 2}
        if rank.get(tag, 9) < rank.get(prev, 9):
            seen[name] = tag
    for name, tag in seen.items():
        by_tag[tag].append(name)
    for tag in by_tag:
        by_tag[tag] = sorted(set(by_tag[tag]))
    return by_tag


def moon_sentence(rows: list[dict[str, Any]]) -> str:
    moons = [r for r in rows if r["kind"] == "moon"]
    if not moons:
        return "Moon not computed."
    r = moons[0]
    pct = int(round(float(r.get("illumination") or 0) * 100))
    phase = r.get("phase_name") or "unknown phase"
    if float(r["alt_deg"]) < 0 or r.get("obscured"):
        return f"Moon {phase}, {pct}% lit, below the terrain horizon."
    wash = ""
    if pct >= 50 and float(r["alt_deg"]) > 10:
        wash = " Bright enough to wash out the Milky Way and faint constellations."
    return f"Moon {phase}, {pct}% lit, {fmt_altaz(r['alt_deg'], r['az_deg'])}.{wash}"


def milky_way_sentence(rows: list[dict[str, Any]]) -> str:
    feats = [r for r in rows if r["kind"] == "feature" and r["name"] == "Milky Way centre"]
    if not feats:
        return ""
    r = feats[0]
    if float(r["alt_deg"]) < 0 or r.get("obscured"):
        return "Milky Way centre is below the local horizon."
    return f"Milky Way centre {fmt_altaz(r['alt_deg'], r['az_deg'])}."


def nav_star_lines(rows: list[dict[str, Any]]) -> list[str]:
    stars = [
        r
        for r in rows
        if r["kind"] == "star" and r["name"] in NAV_STARS and visible(r, min_alt=5)
    ]
    stars.sort(key=lambda r: (r.get("mag") is None, r.get("mag") if r.get("mag") is not None else 99))
    lines = []
    for r in stars[:12]:
        mag = f", mag {r['mag']:.1f}" if r.get("mag") is not None else ""
        lines.append(f"- {r['name']} ({r['constellation']}): {fmt_altaz(r['alt_deg'], r['az_deg'])}{mag}")
    return lines


def sample_heading(sample: dict[str, Any]) -> str:
    return (
        f"{fmt_time(sample['time'])} · elapsed {fmt_hours(sample['elapsed_h'])} · "
        f"km {sample['dist_km']:.1f} · {sample['elev_m']:.0f} m"
    )


def md_image(stem: str, plots: dict[str, str] | None, alt: str) -> list[str]:
    if not plots or stem not in plots:
        return []
    return ["", f"![{alt}]({plots[stem]})", ""]


def build_markdown(
    cfg: dict[str, Any],
    nights: dict[str, Any],
    samples: list[dict[str, Any]],
    sky: list[dict[str, Any]],
    plots: dict[str, str] | None = None,
) -> str:
    race = cfg.get("race") or {}
    title = race.get("name") or "Race"
    pace = nights.get("pace_kmh")
    lines: list[str] = [
        f"# {title} — night sky notes",
        "",
        f"Times are {nights.get('timezone') or 'local'}. "
        f"Positions assume even pace to cutoff"
        + (f" ({pace:.2f} km/h)" if pace else "")
        + ". Faster running puts you further along the course at the same clock time; "
        "planet positions barely change across the course, terrain horizon does.",
        "",
        DEM_LIMITS_NOTE,
        "",
        "## Night windows",
        "",
        "| Night | Astro dusk | Astro dawn | Length | Elapsed | km (cutoff pace) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for n in nights.get("nights") or []:
        lines.append(
            f"| {n['night_id']} | {fmt_time(n['start'])} | {fmt_time(n['end'])} | "
            f"{fmt_hours(n['duration_h'])} | {fmt_hours(n['elapsed0_h'])}–{fmt_hours(n['elapsed1_h'])} | "
            f"{n['dist0_km']:.0f}–{n['dist1_km']:.0f} |"
        )
    lines += ["", "### Twilight (context)", "", "| Event | Local time | Elapsed |", "| --- | --- | --- |"]
    wanted = {
        "sunset",
        "civil_dusk",
        "nautical_dusk",
        "astronomical_dusk",
        "astronomical_dawn",
        "nautical_dawn",
        "civil_dawn",
        "sunrise",
    }
    for e in nights.get("events") or []:
        if e["event"] not in wanted:
            continue
        lines.append(f"| {e['event'].replace('_', ' ')} | {fmt_time(e['time'])} | {fmt_hours(e['elapsed_h'])} |")
    lines.extend(md_image("course", plots, "Course with night samples"))
    lines.extend(md_image("profile", plots, "Elevation profile with night windows"))

    by_night: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for s in samples:
        by_night[int(s["night_id"])].append(s)
    keys = {s["i"] for s in key_samples(samples)}

    for n in nights.get("nights") or []:
        nid = int(n["night_id"])
        lines += ["", f"## Night {nid}", ""]
        group = by_night.get(nid) or []
        if not group:
            lines.append("No along-track samples in this window at cutoff pace.")
            continue
        lines.append(
            f"{fmt_time(n['start'])} → {fmt_time(n['end'])} "
            f"(elapsed {fmt_hours(n['elapsed0_h'])}–{fmt_hours(n['elapsed1_h'])}, "
            f"km {n['dist0_km']:.0f}–{n['dist1_km']:.0f} at cutoff pace)."
        )
        lines.extend(md_image(f"night{nid}-alt", plots, f"Night {nid} altitude"))
        for sample in group:
            if sample["i"] not in keys:
                continue
            rows = rows_for_sample(sky, sample["i"])
            lines += ["", f"### {sample_heading(sample)}", ""]
            lines.extend(md_image(disc_stem(sample, group), plots, sample_heading(sample)))
            lines.append(moon_sentence(rows))
            mw = milky_way_sentence(rows)
            if mw:
                lines.append("")
                lines.append(mw)
            lines += ["", "**Planets**", ""]
            lines.extend(planet_lines(rows) or ["- none above the geometric horizon"])
            groups = constellation_groups(rows)
            lines += ["", "**Constellations**", ""]
            if groups["overhead"]:
                lines.append(f"- Overhead: {', '.join(groups['overhead'])}")
            if groups["up"]:
                lines.append(f"- Up: {', '.join(groups['up'])}")
            if groups["rising"]:
                lines.append(f"- Rising: {', '.join(groups['rising'])}")
            if groups["setting"]:
                lines.append(f"- Setting: {', '.join(groups['setting'])}")
            nav = nav_star_lines(rows)
            if nav:
                lines += ["", "**Bright stars**", ""]
                lines.extend(nav)

        lines += ["", "### All night samples (cutoff pace)", "", "| Local | Elapsed | km | Elev | Heading |", "| --- | --- | --- | --- | --- |"]
        for sample in group:
            lines.append(
                f"| {fmt_time(sample['time'])} | {fmt_hours(sample['elapsed_h'])} | "
                f"{sample['dist_km']:.1f} | {sample['elev_m']:.0f} m | {sample['heading_deg']:.0f}° |"
            )

    lines += ["", "## Notes", "", "- Astronomical night is Sun altitude below −18°.", "- Horizon masking uses GLO-30 plus a 2° buffer; a planet behind a ridge is flagged, not hidden from the CSV.", "- This is pre-computation for study, not a live planetarium.", ""]
    return "\n".join(lines) + "\n"


def flatten_nights(nights: dict[str, Any]) -> list[dict[str, Any]]:
    return list(nights.get("nights") or [])


def main() -> None:
    parser = argparse.ArgumentParser(description="Write markdown and CSV night-sky notes.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    datadir = data_dir(args.data_dir)
    out_dir = datadir / "out"
    nights = load_json(datadir / "nights.json")
    samples = load_json(datadir / "samples.json")
    sky = load_json(datadir / "sky.json")
    formats = (cfg.get("output") or {}).get("format") or ["markdown", "csv"]
    if "markdown" in formats:
        plot_links = {
            p.stem: f"plots/{p.name}" for p in sorted((out_dir / "plots").glob("*.png"))
        }
        md = build_markdown(cfg, nights, samples, sky, plots=plot_links or None)
        ensure_parent(out_dir / "summary.md")
        (out_dir / "summary.md").write_text(md, encoding="utf-8")
    if "csv" in formats:
        write_csv(
            out_dir / "nights.csv",
            flatten_nights(nights),
            ["night_id", "start", "end", "duration_h", "elapsed0_h", "elapsed1_h", "dist0_km", "dist1_km"],
        )
        write_csv(
            out_dir / "samples.csv",
            samples,
            ["i", "night_id", "time", "elapsed_h", "dist_km", "lat", "lon", "elev_m", "heading_deg"],
        )
        write_csv(
            out_dir / "sky.csv",
            sky,
            [
                "sample_i",
                "night_id",
                "time",
                "dist_km",
                "kind",
                "name",
                "constellation",
                "alt_deg",
                "az_deg",
                "mag",
                "horizon_deg",
                "obscured",
                "tag",
                "illumination",
                "phase_name",
            ],
        )
    print(out_dir)


if __name__ == "__main__":
    main()
