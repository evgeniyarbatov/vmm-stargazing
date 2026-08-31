from __future__ import annotations

import argparse
import html
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from catalog import NAV_STARS
from config import REPO_ROOT, data_dir, load_config
from utils import DEM_LIMITS_NOTE, compass8, dump_json, load_json

REPO_URL = "https://github.com/evgeniyarbatov/vmm-stargazing"


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


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


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


def sample_stem(sample: dict[str, Any]) -> str:
    return f"night{int(sample['night_id'])}-s{int(sample['i'])}"


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


def planet_items(rows: list[dict[str, Any]]) -> list[str]:
    planets = [r for r in rows if r["kind"] == "planet" and float(r["alt_deg"]) >= 0]
    items = []
    for r in planets:
        mag = f", mag {r['mag']:.1f}" if r.get("mag") is not None else ""
        extra = " — behind terrain" if r.get("obscured") else ""
        items.append(
            f"<li><strong>{esc(r['name'])}</strong>: "
            f"{esc(fmt_altaz(r['alt_deg'], r['az_deg']))}{esc(mag)}{esc(extra)}</li>"
        )
    return items


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


def nav_star_items(rows: list[dict[str, Any]]) -> list[str]:
    stars = [
        r for r in rows if r["kind"] == "star" and r["name"] in NAV_STARS and visible(r, min_alt=5)
    ]
    stars.sort(
        key=lambda r: (r.get("mag") is None, r.get("mag") if r.get("mag") is not None else 99)
    )
    items = []
    for r in stars[:12]:
        mag = f", mag {r['mag']:.1f}" if r.get("mag") is not None else ""
        items.append(
            f"<li>{esc(r['name'])} ({esc(r['constellation'])}): "
            f"{esc(fmt_altaz(r['alt_deg'], r['az_deg']))}{esc(mag)}</li>"
        )
    return items


def sample_heading(sample: dict[str, Any]) -> str:
    return (
        f"{fmt_time(sample['time'])} · elapsed {fmt_hours(sample['elapsed_h'])} · "
        f"km {sample['dist_km']:.1f} · {sample['elev_m']:.0f} m"
    )


def sky_lede(rows: list[dict[str, Any]]) -> str:
    parts = [moon_sentence(rows)]
    mw = milky_way_sentence(rows)
    if mw:
        parts.append(mw)
    groups = constellation_groups(rows)
    if groups["overhead"]:
        parts.append(f"Overhead: {', '.join(groups['overhead'])}.")
    return " ".join(parts)


def html_ul(items: list[str], empty: str) -> list[str]:
    if not items:
        return [f"<p class='empty'>{esc(empty)}</p>"]
    return ["<ul>", *[f"  {item}" for item in items], "</ul>"]


def html_figure(stem: str, plots: dict[str, str] | None, alt: str, caption: str = "") -> list[str]:
    if not plots or stem not in plots:
        return []
    src = plots[stem]
    name = Path(src).name
    loading = "eager" if stem == "course" else "lazy"
    lines = [
        "<figure>",
        f'  <img src="{esc(src)}" alt="{esc(alt)}" loading="{loading}" />',
        "  <figcaption>",
    ]
    if caption:
        lines.append(f"    <span>{esc(caption)}</span>")
    lines += [
        f'    <a href="{esc(src)}" download="{esc(name)}">Download chart</a>',
        "  </figcaption>",
        "</figure>",
    ]
    return lines


def html_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["<div class='table-wrap'><table>", "  <thead><tr>"]
    lines.extend(f"    <th>{esc(h)}</th>" for h in headers)
    lines += ["  </tr></thead>", "  <tbody>"]
    for row in rows:
        lines.append("    <tr>")
        lines.extend(f"      <td>{esc(cell)}</td>" for cell in row)
        lines.append("    </tr>")
    lines += ["  </tbody>", "</table></div>"]
    return lines


def constellation_block(rows: list[dict[str, Any]]) -> list[str]:
    groups = constellation_groups(rows)
    items = []
    for label, key in (
        ("Overhead", "overhead"),
        ("Up", "up"),
        ("Rising", "rising"),
        ("Setting", "setting"),
    ):
        if groups[key]:
            items.append(f"<li>{label}: {esc(', '.join(groups[key]))}</li>")
    lines = ["<h4>Constellations</h4>"]
    lines.extend(html_ul(items, "none tagged in this snapshot"))
    return lines


def build_html(
    cfg: dict[str, Any],
    nights: dict[str, Any],
    samples: list[dict[str, Any]],
    sky: list[dict[str, Any]],
    plots: dict[str, str] | None = None,
) -> str:
    race = cfg.get("race") or {}
    title = race.get("name") or "Race"
    location = race.get("location") or ""
    pace = nights.get("pace_kmh")
    tz = nights.get("timezone") or "local"
    pace_note = f" ({pace:.2f} km/h)" if pace else ""
    pace_model = nights.get("pace_model") or "even"
    if pace_model == "checkpoints":
        pace_line = (
            "Positions follow the published checkpoint cutoffs. "
            "Faster running puts you further along the course at the same clock "
            "time; planet positions barely change across the course, terrain horizon does."
        )
    else:
        pace_line = (
            f"Positions assume even pace to cutoff{pace_note}. "
            "Faster running puts you further along the course at the same clock "
            "time; planet positions barely change across the course, terrain horizon does."
        )
    night_list = list(nights.get("nights") or [])

    lines: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8" />',
        '  <meta name="viewport" content="width=device-width, initial-scale=1" />',
        f"  <title>{esc(title)} — night sky</title>",
        '  <link rel="stylesheet" href="style.css" />',
        "</head>",
        "<body>",
        "  <header>",
        f'    <p class="kicker">{esc(location + " · " if location else "")}{esc(title)}</p>',
        "    <h1>Look up.</h1>",
        "    <p class='lede'>Two nights on the Hoàng Liên Sơn. If you stop, this is what is "
        "overhead — planets, a turning sky, and a few ridges worth remembering.</p>",
        f"    <p class='meta'>Times are {esc(tz)}. {esc(pace_line)}</p>",
        f"    <p class='meta'>{esc(DEM_LIMITS_NOTE)}</p>",
        "  </header>",
        "  <main>",
    ]

    if len(night_list) > 1:
        lines.append('    <nav class="nights">')
        for n in night_list:
            nid = int(n["night_id"])
            lines.append(f'      <a href="#night-{nid}">Night {nid}</a>')
        lines.append("    </nav>")

    lines += ["    <section>", "      <h2>Night windows</h2>"]
    lines.extend(
        html_table(
            ["Night", "Astro dusk", "Astro dawn", "Length", "Elapsed", "km (cutoff pace)"],
            [
                [
                    str(n["night_id"]),
                    fmt_time(n["start"]),
                    fmt_time(n["end"]),
                    fmt_hours(n["duration_h"]),
                    f"{fmt_hours(n['elapsed0_h'])}–{fmt_hours(n['elapsed1_h'])}",
                    f"{n['dist0_km']:.0f}–{n['dist1_km']:.0f}",
                ]
                for n in night_list
            ],
        )
    )

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
    twilight_rows = [
        [e["event"].replace("_", " "), fmt_time(e["time"]), fmt_hours(e["elapsed_h"])]
        for e in nights.get("events") or []
        if e["event"] in wanted
    ]
    if twilight_rows:
        lines.append("      <details><summary>Twilight (context)</summary>")
        lines.extend(html_table(["Event", "Local time", "Elapsed"], twilight_rows))
        lines.append("      </details>")

    lines.extend(html_figure("course", plots, "Course with night samples"))
    lines.extend(html_figure("profile", plots, "Elevation profile with night windows"))
    lines.extend(
        html_figure(
            "spots",
            plots,
            "Stargazing spot scores along the course",
            "Score mixes open DEM horizon, elevation, moon (down/dim is better), "
            "and whether the Milky Way centre is above the ridge.",
        )
    )
    lines.append("    </section>")

    by_night: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for s in samples:
        by_night[int(s["night_id"])].append(s)

    for n in night_list:
        nid = int(n["night_id"])
        group = by_night.get(nid) or []
        lines += [
            f'    <section id="night-{nid}">',
            f"      <h2>Night {nid}</h2>",
            f"      <p>{esc(fmt_time(n['start']))} → {esc(fmt_time(n['end']))} "
            f"(elapsed {esc(fmt_hours(n['elapsed0_h']))}–{esc(fmt_hours(n['elapsed1_h']))}, "
            f"km {n['dist0_km']:.0f}–{n['dist1_km']:.0f} at cutoff pace).</p>",
        ]
        if not group:
            lines.append("      <p>No along-track samples in this window at cutoff pace.</p>")
            lines.append("    </section>")
            continue
        mid = min(group, key=midnightish)
        lines.append(f"      <p class='lede'>{esc(sky_lede(rows_for_sample(sky, mid['i'])))}</p>")
        lines.extend(
            html_figure(f"night{nid}-alt-planets", plots, f"Night {nid} planets and moon")
        )
        lines.extend(html_figure(f"night{nid}-alt-stars", plots, f"Night {nid} bright stars"))
        for sample in group:
            rows = rows_for_sample(sky, sample["i"])
            stem = sample_stem(sample)
            lines += [f"      <h3>{esc(sample_heading(sample))}</h3>"]
            lines.extend(html_figure(stem, plots, sample_heading(sample)))
            lines.extend(
                html_figure(
                    f"{stem}-ahead",
                    plots,
                    f"{sample_heading(sample)} looking along the course",
                    "GLO-30 DSM looking up the GPX. "
                    "The filled contour is the ridge; a star below it is behind terrain.",
                )
            )
            lines.append(f"      <p>{esc(moon_sentence(rows))}</p>")
            mw = milky_way_sentence(rows)
            if mw:
                lines.append(f"      <p>{esc(mw)}</p>")
            lines.append("      <h4>Planets</h4>")
            lines.extend(html_ul(planet_items(rows), "none above the geometric horizon"))
            lines.extend(constellation_block(rows))
            nav = nav_star_items(rows)
            if nav:
                lines.append("      <h4>Bright stars</h4>")
                lines.extend(html_ul(nav, ""))
        lines.append("    </section>")

    lines += [
        "  </main>",
        "  <footer>",
        "    <p>Pre-computation for study, not a live planetarium. Astronomical night is "
        "Sun altitude below −18°. Horizon masking uses GLO-30 plus a 2° buffer.</p>",
        "    <p>",
        '      <a href="data.json" download="vmm-stargazing.json">Download raw data (JSON)</a>',
        f'      <a href="{REPO_URL}">Source</a>',
        f'      <a href="{REPO_URL}/blob/main/ROADMAP.md">Roadmap</a>',
        "    </p>",
        "  </footer>",
        "</body>",
        "</html>",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the GitHub Pages night-sky site.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--site-dir", type=Path, default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    datadir = data_dir(args.data_dir)
    site_dir = (args.site_dir or REPO_ROOT / "docs").expanduser()
    nights = load_json(datadir / "nights.json")
    samples = load_json(datadir / "samples.json")
    sky = load_json(datadir / "sky.json")
    plot_links = {p.stem: f"plots/{p.name}" for p in sorted((site_dir / "plots").glob("*.png"))}
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "index.html").write_text(
        build_html(cfg, nights, samples, sky, plots=plot_links or None),
        encoding="utf-8",
    )
    dump_json(
        site_dir / "data.json",
        {
            "race": cfg.get("race") or {},
            "nights": nights,
            "samples": samples,
            "sky": sky,
        },
    )
    print(site_dir)


if __name__ == "__main__":
    main()
