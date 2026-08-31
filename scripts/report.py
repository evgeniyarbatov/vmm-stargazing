from __future__ import annotations

import argparse
import html
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from catalog import NAV_STARS, PLANETS
from config import REPO_ROOT, data_dir, load_config
from sky_links import sky_entry
from utils import DEM_LIMITS_NOTE, compass8, dump_json, load_json

REPO_URL = "https://github.com/evgeniyarbatov/vmm-stargazing"
AHEAD_CAPTION = (
    "GLO-30 DSM looking up the GPX. "
    "The filled contour is the horizon; a star below it is behind terrain."
)
HASH_SCRIPT = """  <script>
    function openTarget() {
      var id = location.hash.slice(1);
      if (!id) return;
      var el = document.getElementById(id);
      if (!el) return;
      if (el.tagName === 'DETAILS') el.open = true;
      var parent = el.closest('details');
      if (parent) parent.open = true;
    }
    openTarget();
    window.addEventListener('hashchange', openTarget);
    document.addEventListener('click', function (e) {
      if (e.target.closest('summary a')) e.stopPropagation();
    }, true);
  </script>"""


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


def planet_items(rows: list[dict[str, Any]], nv: NightView | None = None) -> list[str]:
    planets = [r for r in rows if r["kind"] == "planet" and float(r["alt_deg"]) >= 0]
    items = []
    for r in planets:
        mag = f", mag {r['mag']:.1f}" if r.get("mag") is not None else ""
        extra = " — behind terrain" if r.get("obscured") else ""
        items.append(
            f"<li><strong>{linked_site_name(r['name'], nv=nv)}</strong>: "
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


def moon_sentence(rows: list[dict[str, Any]], nv: NightView | None = None) -> str:
    moons = [r for r in rows if r["kind"] == "moon"]
    if not moons:
        return f"{linked_site_name('Moon', nv=nv)} not computed."
    r = moons[0]
    pct = int(round(float(r.get("illumination") or 0) * 100))
    phase = r.get("phase_name") or "unknown phase"
    moon = linked_site_name("Moon", nv=nv)
    if float(r["alt_deg"]) < 0 or r.get("obscured"):
        return f"{moon} {esc(phase)}, {pct}% lit, below the terrain horizon."
    wash = ""
    if pct >= 50 and float(r["alt_deg"]) > 10:
        wash = " Bright enough to wash out the Milky Way and faint constellations."
    return (
        f"{moon} {esc(phase)}, {pct}% lit, "
        f"{esc(fmt_altaz(r['alt_deg'], r['az_deg']))}.{esc(wash)}"
    )


def milky_way_sentence(rows: list[dict[str, Any]], nv: NightView | None = None) -> str:
    feats = [r for r in rows if r["kind"] == "feature" and r["name"] == "Milky Way centre"]
    if not feats:
        return ""
    r = feats[0]
    name = linked_site_name("Milky Way centre", nv=nv)
    if float(r["alt_deg"]) < 0 or r.get("obscured"):
        return f"{name} is below the local horizon."
    return f"{name} {esc(fmt_altaz(r['alt_deg'], r['az_deg']))}."


def constellation_id(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name)
    ascii_name = folded.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def altitude_stem(night_id: int, kind: str, name: str) -> str:
    return f"night{int(night_id)}-alt-{kind}-{constellation_id(name)}"


def altitude_name(stem: str, night_id: int) -> str:
    prefix = f"night{int(night_id)}-alt-"
    rest = stem.removeprefix(prefix)
    _kind, _, slug = rest.partition("-")
    return slug.replace("-", " ").title()


def altitude_stems(plots: dict[str, str] | None, night_id: int, series: str) -> list[str]:
    if not plots:
        return []
    kinds = ("planet", "moon") if series == "planets" else ("star",)
    planet_slugs = [constellation_id(p[0]) for p in PLANETS]
    out: list[str] = []
    for kind in kinds:
        prefix = f"night{int(night_id)}-alt-{kind}-"
        found = [stem for stem in plots if stem.startswith(prefix)]
        if kind == "planet":
            found.sort(
                key=lambda stem: planet_slugs.index(stem.removeprefix(prefix))
                if stem.removeprefix(prefix) in planet_slugs
                else 99
            )
        else:
            found.sort()
        out.extend(found)
    return out


def sky_plot_ids(plots: dict[str, str] | None, night_id: int) -> set[str]:
    return {
        constellation_id(altitude_name(stem, night_id))
        for series in ("planets", "stars")
        for stem in altitude_stems(plots, night_id, series)
    }


def html_altitude_block(
    night_id: int, plots: dict[str, str] | None, series: str
) -> list[str]:
    stems = altitude_stems(plots, night_id, series)
    if not stems:
        return []
    heading = "Planets and moon" if series == "planets" else "Bright stars"
    lines = [f"<h3>{esc(heading)}</h3>"]
    jump = []
    figs: list[str] = []
    for stem in stems:
        name = altitude_name(stem, night_id)
        html_id = constellation_id(name)
        jump.append(f'<a href="#{esc(html_id)}">{esc(name)}</a>')
        figs.append(f'<h4 id="{esc(html_id)}">{titled_name(name)}</h4>')
        figs.extend(html_figure(stem, plots, f"Night {night_id} · {name}"))
    if len(jump) > 1:
        lines.append(f"<p class='jump'>{' · '.join(jump)}</p>")
    lines.extend(figs)
    return lines


def linked_site_name(name: str, nv: NightView | None = None) -> str:
    cid = constellation_id(name)
    if nv is not None and nv.iau_href and cid in nv.iau_ids:
        return f'<a href="{esc(nv.iau_href)}#{esc(cid)}">{esc(name)}</a>'
    if nv is not None and cid in nv.sky_ids:
        return f'<a href="{esc(nv.sky_href)}#{esc(cid)}">{esc(name)}</a>'
    return esc(name)


def encyclopedia_links(name: str) -> str:
    entry = sky_entry(name)
    grok = entry["grokipedia"]
    wiki = entry["wikipedia"]
    bits: list[str] = []
    if grok != wiki:
        bits.append(
            f'<a href="{esc(grok)}" target="_blank" rel="noopener noreferrer">Grokipedia</a>'
        )
    bits.append(
        f'<a href="{esc(wiki)}" target="_blank" rel="noopener noreferrer">Wikipedia</a>'
    )
    return " · ".join(bits)


def titled_name(name: str) -> str:
    return f"{esc(name)} <span class=\"ency\">{encyclopedia_links(name)}</span>"


def unique_ref_names(names: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for name in names:
        cid = constellation_id(name)
        if cid in seen:
            continue
        seen.add(cid)
        out.append(name)
    out.sort(key=lambda n: n.lower())
    return out


def sample_ref_names(rows: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    if any(r["kind"] == "moon" for r in rows):
        names.append("Moon")
    if any(r["kind"] == "feature" and r["name"] == "Milky Way centre" for r in rows):
        names.append("Milky Way centre")
    for r in rows:
        if r["kind"] == "planet" and float(r["alt_deg"]) >= 0:
            names.append(r["name"])
    groups = constellation_groups(rows)
    for key in ("overhead", "up", "rising", "setting"):
        names.extend(groups[key])
    for r in rows:
        if r["kind"] == "star" and r["name"] in NAV_STARS and visible(r, min_alt=5):
            names.append(r["name"])
    return names


def references_block(names: list[str]) -> list[str]:
    ordered = unique_ref_names(names)
    if not ordered:
        return []
    lines = ["<h3>References</h3>", "<ul class='refs'>"]
    for name in ordered:
        lines.append(f"  <li>{esc(name)} · {encyclopedia_links(name)}</li>")
    lines.append("</ul>")
    return lines


def join_linked(names: list[str], nv: NightView | None = None) -> str:
    return ", ".join(linked_site_name(n, nv) for n in names)


def name_in(title: str, names: set[str]) -> bool:
    tid = constellation_id(title)
    return any(constellation_id(n) == tid for n in names)


def nav_star_items(rows: list[dict[str, Any]], nv: NightView | None = None) -> list[str]:
    stars = [
        r for r in rows if r["kind"] == "star" and r["name"] in NAV_STARS and visible(r, min_alt=5)
    ]
    stars.sort(
        key=lambda r: (r.get("mag") is None, r.get("mag") if r.get("mag") is not None else 99)
    )
    items = []
    for r in stars[:12]:
        mag = f", mag {r['mag']:.1f}" if r.get("mag") is not None else ""
        constel = linked_site_name(r["constellation"], nv)
        items.append(
            f"<li>{linked_site_name(r['name'], nv)} ({constel}): "
            f"{esc(fmt_altaz(r['alt_deg'], r['az_deg']))}{esc(mag)}</li>"
        )
    return items


def sample_heading(sample: dict[str, Any]) -> str:
    return (
        f"{fmt_time(sample['time'])} · elapsed {fmt_hours(sample['elapsed_h'])} · "
        f"km {sample['dist_km']:.1f} · {sample['elev_m']:.0f} m"
    )


def km_label(dist_km: float) -> str:
    return f"km {int(round(dist_km))}"


def nights_phrase(n: int) -> str:
    if n == 1:
        return "One night"
    if n == 2:
        return "Two nights"
    return f"{n} nights"


def fmt_step_km(metres: float) -> str:
    km = metres / 1000.0
    if abs(km - round(km)) < 0.05:
        return f"{int(round(km))} km"
    return f"{km:.1f} km"


def sample_step_m(cfg: dict[str, Any]) -> float:
    raw = (cfg.get("sampling") or {}).get("distance_m")
    return float(raw) if raw else 2000.0


def sky_lede(rows: list[dict[str, Any]], nv: NightView | None = None) -> str:
    parts = [moon_sentence(rows, nv)]
    mw = milky_way_sentence(rows, nv)
    if mw:
        parts.append(mw)
    groups = constellation_groups(rows)
    if groups["overhead"]:
        parts.append(f"Overhead: {join_linked(groups['overhead'], nv)}.")
    return " ".join(parts)


def html_ul(items: list[str], empty: str) -> list[str]:
    if not items:
        return [f"<p class='empty'>{esc(empty)}</p>"]
    return ["<ul>", *[f"  {item}" for item in items], "</ul>"]


def html_src_figure(
    src: str, alt: str, caption: str = "", loading: str = "lazy", css: str = ""
) -> list[str]:
    tag = f'<figure class="{esc(css)}">' if css else "<figure>"
    lines = [
        tag,
        f'  <img src="{esc(src)}" alt="{esc(alt)}" loading="{loading}" />',
    ]
    if caption:
        lines.append(f"  <figcaption>{esc(caption)}</figcaption>")
    lines.append("</figure>")
    return lines


def html_figure(stem: str, plots: dict[str, str] | None, alt: str, caption: str = "") -> list[str]:
    if not plots or stem not in plots:
        return []
    loading = "eager" if stem == "course" else "lazy"
    return html_src_figure(plots[stem], alt, caption=caption, loading=loading)


IauFiles = list[tuple[str, str]]
IauConstellation = tuple[str, IauFiles]
IAU_PANEL_LABELS = (("map", "IAU chart"), ("az", "Azimuth"), ("alt", "Altitude"))


def group_iau_pngs(folder: Path) -> list[IauConstellation]:
    by_base: dict[str, dict[str, Path]] = defaultdict(dict)
    for png in sorted(folder.glob("*.png")):
        stem = png.stem
        kind = "map"
        base = stem
        if stem.endswith("-az"):
            kind, base = "az", stem[: -len("-az")]
        elif stem.endswith("-alt"):
            kind, base = "alt", stem[: -len("-alt")]
        by_base[base][kind] = png
    items: list[IauConstellation] = []
    for base in sorted(by_base):
        files: IauFiles = []
        for kind, label in IAU_PANEL_LABELS:
            png = by_base[base].get(kind)
            if png is None:
                continue
            files.append((label, f"plots/constellations/{folder.name}/{png.name}"))
        if files:
            items.append((base.replace("_", " "), files))
    return items


def iau_plot_gallery(site_dir: Path) -> dict[int, list[IauConstellation]]:
    root = site_dir / "plots" / "constellations"
    out: dict[int, list[IauConstellation]] = {}
    if not root.is_dir():
        return out
    for folder in sorted(root.glob("night*")):
        try:
            nid = int(folder.name.removeprefix("night"))
        except ValueError:
            continue
        items = group_iau_pngs(folder)
        if items:
            out[nid] = items
    return out


def html_details(
    summary: str,
    body: list[str],
    *,
    opened: bool = False,
    html_id: str | None = None,
    css: str = "",
    summary_html: bool = False,
) -> list[str]:
    attrs: list[str] = []
    if html_id:
        attrs.append(f'id="{esc(html_id)}"')
    if css:
        attrs.append(f'class="{esc(css)}"')
    if opened:
        attrs.append("open")
    attr = f" {' '.join(attrs)}" if attrs else ""
    label = summary if summary_html else esc(summary)
    return [f"<details{attr}>", f"  <summary>{label}</summary>", *body, "</details>"]


def html_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["<div class='table-wrap'><table>", "  <thead><tr>"]
    lines.extend(f"    <th>{esc(h)}</th>" for h in headers)
    lines += ["  </tr></thead>", "  <tbody>"]
    for row in rows:
        lines.append("    <tr>")
        for header, cell in zip(headers, row, strict=False):
            lines.append(f'      <td data-label="{esc(header)}">{esc(cell)}</td>')
        lines.append("    </tr>")
    lines += ["  </tbody>", "</table></div>"]
    return lines


def constellation_block(rows: list[dict[str, Any]], nv: NightView | None = None) -> list[str]:
    groups = constellation_groups(rows)
    items = []
    for label, key in (
        ("Overhead", "overhead"),
        ("Up", "up"),
        ("Rising", "rising"),
        ("Setting", "setting"),
    ):
        if groups[key]:
            items.append(f"<li>{label}: {join_linked(groups[key], nv)}</li>")
    lines = ["<h4>Constellations</h4>"]
    lines.extend(html_ul(items, "none tagged in this snapshot"))
    return lines


def pace_line(nights: dict[str, Any]) -> str:
    pace = nights.get("pace_kmh")
    pace_note = f" ({pace:.2f} km/h)" if pace else ""
    pace_model = nights.get("pace_model") or "even"
    if pace_model == "scenarios":
        scenario = nights.get("pace_scenario") or "realistic"
        return (
            f"Maps use the {scenario} predicted pace "
            "(optimistic / realistic / conservative from a calibrated 100 K model). "
            "Faster running puts you further along the course at the same clock "
            "time; planet positions barely change across the course, terrain horizon does."
        )
    if pace_model == "checkpoints":
        return (
            "Positions follow the published checkpoint cutoffs. "
            "Faster running puts you further along the course at the same clock "
            "time; planet positions barely change across the course, terrain horizon does."
        )
    return (
        f"Positions assume even pace to cutoff{pace_note}. "
        "Faster running puts you further along the course at the same clock "
        "time; planet positions barely change across the course, terrain horizon does."
    )


def night_window_text(n: dict[str, Any]) -> str:
    return (
        f"{fmt_time(n['start'])} → {fmt_time(n['end'])} "
        f"(elapsed {fmt_hours(n['elapsed0_h'])}–{fmt_hours(n['elapsed1_h'])}, "
        f"km {n['dist0_km']:.0f}–{n['dist1_km']:.0f} at predicted pace)"
    )


def night_span_text(n: dict[str, Any]) -> str:
    return (
        f"{fmt_time(n['start'])} → {fmt_time(n['end'])} · "
        f"km {n['dist0_km']:.0f}–{n['dist1_km']:.0f}"
    )


def pick_ordered(
    nid: int,
    group: list[dict[str, Any]],
    spots: list[dict[str, Any]] | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    night_spots = [s for s in (spots or []) if int(s["night_id"]) == nid]
    by_i = {int(s["i"]): s for s in group}
    if night_spots:
        featured = by_i.get(int(max(night_spots, key=lambda r: float(r["score"]))["i"]))
        ordered = [by_i[int(s["i"])] for s in night_spots if int(s["i"]) in by_i]
    else:
        featured = min(group, key=midnightish) if group else None
        ordered = list(group)
    if featured is None and group:
        featured = min(group, key=midnightish)
    return featured, ordered


def assign_stop_hrefs(ordered: list[dict[str, Any]]) -> dict[int, str]:
    used: set[str] = set()
    out: dict[int, str] = {}
    for s in ordered:
        nid = int(s["night_id"])
        name = f"night-{nid}-km{int(round(float(s['dist_km'])))}.html"
        if name in used:
            name = f"night-{nid}-km{int(round(float(s['dist_km'])))}-s{int(s['i'])}.html"
        used.add(name)
        out[int(s["i"])] = name
    return out


def visible_iau_names(ordered: list[dict[str, Any]], sky: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for s in ordered:
        groups = constellation_groups(rows_for_sample(sky, int(s["i"])))
        names.update(groups["overhead"])
        names.update(groups["up"])
    return names


def filter_iau_items(
    items: list[IauConstellation], visible_names: set[str]
) -> list[IauConstellation]:
    ids = {constellation_id(n) for n in visible_names}
    return [(title, files) for title, files in items if constellation_id(title) in ids]


def sample_disc_figures(sample: dict[str, Any], plots: dict[str, str] | None) -> list[str]:
    stem = sample_stem(sample)
    lines = html_figure(stem, plots, sample_heading(sample))
    lines.extend(
        html_figure(
            f"{stem}-ahead",
            plots,
            f"{sample_heading(sample)} looking along the course",
            AHEAD_CAPTION,
        )
    )
    return lines


def sample_sky_lists(rows: list[dict[str, Any]], nv: NightView | None = None) -> list[str]:
    lines = ["<h4>Planets</h4>"]
    lines.extend(html_ul(planet_items(rows, nv), "none above the geometric horizon"))
    lines.extend(constellation_block(rows, nv))
    nav = nav_star_items(rows, nv)
    if nav:
        lines.append("<h4>Bright stars</h4>")
        lines.extend(html_ul(nav, ""))
    return lines


def html_crumbs(crumbs: list[tuple[str, str | None]]) -> list[str]:
    if not crumbs:
        return []
    bits: list[str] = []
    for i, (label, href) in enumerate(crumbs):
        if href:
            bits.append(f'<a href="{esc(href)}">{esc(label)}</a>')
        else:
            bits.append(f"<span>{esc(label)}</span>")
        if i < len(crumbs) - 1:
            bits.append('<span class="sep" aria-hidden="true">/</span>')
    return [
        '<nav class="crumbs" aria-label="Breadcrumb">',
        "  " + " ".join(bits),
        "</nav>",
    ]


def html_pager(
    prev: tuple[str, str] | None,
    nxt: tuple[str, str] | None,
) -> list[str]:
    if not prev and not nxt:
        return []
    lines = ['<nav class="pager">']
    if prev:
        lines.append(f'  <a class="prev" href="{esc(prev[1])}">{esc(prev[0])}</a>')
    else:
        lines.append("  <span></span>")
    if nxt:
        lines.append(f'  <a class="next" href="{esc(nxt[1])}">{esc(nxt[0])}</a>')
    lines.append("</nav>")
    return lines


def page_shell(
    *,
    title: str,
    heading: str,
    body: list[str],
    kicker: str,
    night_ids: list[int],
    home: bool = False,
    kicker_href: str | None = None,
    crumbs: list[tuple[str, str | None]] | None = None,
    lede: str = "",
    meta_html: list[str] | None = None,
    pager: tuple[tuple[str, str] | None, tuple[str, str] | None] = (None, None),
    spots_gpx: bool = False,
) -> str:
    kicker_html = (
        f'<a href="{esc(kicker_href)}">{esc(kicker)}</a>' if kicker_href else esc(kicker)
    )
    body_class = "home" if home else "page"
    lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8" />',
        '  <meta name="viewport" content="width=device-width, initial-scale=1" />',
        f"  <title>{esc(title)}</title>",
        '  <link rel="stylesheet" href="style.css" />',
        "</head>",
        f'<body class="{body_class}">',
        "  <header>",
        f'    <p class="kicker">{kicker_html}</p>',
    ]
    for ln in html_crumbs(crumbs or []):
        lines.append(f"    {ln}")
    lines.append(f"    <h1>{esc(heading)}</h1>")
    if lede:
        lines.append(f"    <p class='lede'>{esc(lede)}</p>")
    for m in meta_html or []:
        lines.append(f"    <p class='meta'>{m}</p>")
    lines += ["  </header>", "  <main>"]
    lines.extend(body)
    lines.extend(html_pager(pager[0], pager[1]))
    lines += [
        "  </main>",
        "  <footer>",
        "    <p>Pre-computation for study, not a live planetarium. Astronomical night is "
        "Sun altitude below −18°. Horizon masking uses GLO-30 plus a 2° buffer.</p>",
        '    <p class="site-nav">',
        '      <a href="index.html">Contents</a>',
        '      <a href="course.html">Course</a>',
    ]
    for nid in night_ids:
        lines.append(f'      <a href="night-{nid}.html">Night {nid}</a>')
    lines += [
        "    </p>",
        "    <p>",
        '      <a href="data.json" download="vmm-stargazing.json">Download raw data (JSON)</a>',
    ]
    if spots_gpx:
        lines.append(
            '      <a href="stargazing-spots.gpx" download="stargazing-spots.gpx">'
            "Stargazing locations (GPX)</a>"
        )
    lines += [
        f'      <a href="{REPO_URL}">Source</a>',
        f'      <a href="{REPO_URL}/blob/main/ROADMAP.md">Roadmap</a>',
        "    </p>",
        "  </footer>",
        HASH_SCRIPT,
        "</body>",
        "</html>",
        "",
    ]
    return "\n".join(lines)


@dataclass
class NightView:
    rec: dict[str, Any]
    nid: int
    group: list[dict[str, Any]]
    featured: dict[str, Any] | None
    ordered: list[dict[str, Any]]
    href: str
    sky_href: str
    iau_href: str | None
    stop_hrefs: dict[int, str]
    iau_ids: set[str]
    iau_items: list[IauConstellation]
    sky_ids: set[str]


def prepare_night_views(
    night_list: list[dict[str, Any]],
    samples: list[dict[str, Any]],
    sky: list[dict[str, Any]],
    spots: list[dict[str, Any]] | None,
    iau_plots: dict[int, list[IauConstellation]] | None,
    plots: dict[str, str] | None = None,
) -> list[NightView]:
    by_night: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for s in samples:
        by_night[int(s["night_id"])].append(s)
    views: list[NightView] = []
    for n in night_list:
        nid = int(n["night_id"])
        group = by_night.get(nid) or []
        featured, ordered = pick_ordered(nid, group, spots)
        stop_hrefs = assign_stop_hrefs(ordered)
        visible_names = visible_iau_names(ordered, sky)
        items = filter_iau_items((iau_plots or {}).get(nid) or [], visible_names)
        views.append(
            NightView(
                rec=n,
                nid=nid,
                group=group,
                featured=featured,
                ordered=ordered,
                href=f"night-{nid}.html",
                sky_href=f"night-{nid}-sky.html",
                iau_href=f"night-{nid}-iau.html" if items else None,
                stop_hrefs=stop_hrefs,
                iau_ids={constellation_id(title) for title, _ in items},
                iau_items=items,
                sky_ids=sky_plot_ids(plots, nid),
            )
        )
    return views


def other_nights(views: list[NightView], nid: int) -> list[NightView]:
    return [v for v in views if v.nid != nid]


def same_place_html(views: list[NightView], nid: int) -> str:
    others = other_nights(views, nid)
    if not others:
        return ""
    bits: list[str] = []
    for o in others:
        bit = f'<a href="{esc(o.href)}">Night {o.nid}</a>'
        if o.featured is not None:
            href = o.stop_hrefs[int(o.featured["i"])]
            bit += (
                f' · best stop <a href="{esc(href)}">'
                f"{esc(km_label(float(o.featured['dist_km'])))}</a>"
            )
        bits.append(bit)
    return f"<p>Same sky, different place: {', '.join(bits)}.</p>"


def build_index(
    *,
    title: str,
    kicker: str,
    tz: str,
    views: list[NightView],
    sky: list[dict[str, Any]],
    spots_gpx: bool,
) -> str:
    body = [
        '<nav class="toc" aria-label="Contents">',
        "  <ol>",
        "    <li>",
        '      <a href="course.html">Where night falls</a>',
        f"      <p class='insight'>{esc(nights_phrase(len(views)))}, predicted pace.</p>",
        "    </li>",
    ]
    for nv in views:
        body += [
            "    <li>",
            f'      <a href="{esc(nv.href)}">Night {nv.nid}</a>',
            f"      <p class='meta'>{esc(night_span_text(nv.rec))}</p>",
        ]
        if nv.featured is not None:
            body.append(
                f"      <p class='insight'>"
                f"{sky_lede(rows_for_sample(sky, int(nv.featured['i'])), nv)}</p>"
            )
        body.append("      <ol>")
        for s in nv.ordered:
            href = nv.stop_hrefs[int(s["i"])]
            mark = ""
            if nv.featured is not None and int(s["i"]) == int(nv.featured["i"]):
                mark = " — best stop"
            body.append(
                f'        <li><a href="{esc(href)}">'
                f"{esc(km_label(float(s['dist_km'])))}</a>{esc(mark)}</li>"
            )
        body.append(f'        <li><a href="{esc(nv.sky_href)}">Planets and stars</a></li>')
        if nv.iau_href:
            body.append(
                f'        <li><a href="{esc(nv.iau_href)}">Constellations this night</a></li>'
            )
        body += ["      </ol>", "    </li>"]
    body += ["  </ol>", "</nav>"]
    return page_shell(
        title=f"{title} — night sky",
        heading="Look up.",
        body=body,
        kicker=kicker,
        night_ids=[v.nid for v in views],
        home=True,
        lede=(
            f"{nights_phrase(len(views))} on the course. If you stop, this is what is "
            "overhead — planets, a turning sky, and a few places worth remembering."
        ),
        meta_html=[f"Times are {esc(tz)}."],
        spots_gpx=spots_gpx,
    )


def build_course(
    *,
    title: str,
    kicker: str,
    nights: dict[str, Any],
    views: list[NightView],
    plots: dict[str, str] | None,
    spots_gpx: bool,
    sample_m: float = 2000.0,
) -> str:
    night_list = [v.rec for v in views]
    body = [
        f"<p class='lede'>{esc(nights_phrase(len(views)))}, predicted pace. "
        "Open a night when a stop or a name catches you.</p>",
    ]
    finishes = nights.get("pace_finishes_h") or {}
    if finishes:
        bits = []
        for name in ("optimistic", "realistic", "conservative"):
            if name in finishes:
                bits.append(f"{name} {fmt_hours(float(finishes[name]))}")
        if bits:
            body.append(f"<p class='meta'>Predicted finish: {esc(', '.join(bits))}.</p>")
    km_headers = ["Night", "Astro dusk", "Astro dawn", "Length"]
    if any(n.get("scenarios") for n in night_list):
        km_headers += ["Optimistic km", "Realistic km", "Conservative km"]
    else:
        km_headers += ["Elapsed", "km"]
    km_rows = []
    for n in night_list:
        row = [
            str(n["night_id"]),
            fmt_time(n["start"]),
            fmt_time(n["end"]),
            fmt_hours(n["duration_h"]),
        ]
        sc = n.get("scenarios") or {}
        if sc:
            for name in ("optimistic", "realistic", "conservative"):
                block = sc.get(name) or {}
                if block:
                    row.append(f"{block['dist0_km']:.0f}–{block['dist1_km']:.0f}")
                else:
                    row.append("—")
        else:
            row.append(f"{fmt_hours(n['elapsed0_h'])}–{fmt_hours(n['elapsed1_h'])}")
            row.append(f"{n['dist0_km']:.0f}–{n['dist1_km']:.0f}")
        km_rows.append(row)
    body.extend(html_table(km_headers, km_rows))
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
        body.extend(
            html_details(
                "Twilight (context)",
                html_table(["Event", "Local time", "Elapsed"], twilight_rows),
            )
        )
    body.extend(html_figure("course", plots, "Course with night samples"))
    body.extend(html_figure("profile", plots, "Elevation profile with night windows"))
    body.extend(html_figure("spots", plots, "Stargazing spot scores along the course"))
    body.append(
        "<p>While the course is astronomically dark, it is sampled every "
        f"{esc(fmt_step_km(sample_m))}. "
        "Each point is scored for an open DSM horizon, higher ground, a dim or set moon, "
        "and whether the Milky Way centre sits above the local horizon. Aid stations are not used. "
        "The listed places are the highest-scoring points, spaced along the course so closer "
        "samples are the same stretch, not extra stops.</p>"
    )
    if spots_gpx:
        body.append(
            "<p class='meta'><a href='stargazing-spots.gpx' "
            "download='stargazing-spots.gpx'>Download stargazing locations (GPX)</a></p>"
        )
    if views:
        body.append("<h3>Nights</h3>")
        body.append("<ul>")
        for nv in views:
            body.append(
                f'  <li><a href="{esc(nv.href)}">Night {nv.nid}</a> — '
                f"{esc(night_span_text(nv.rec))}</li>"
            )
        body.append("</ul>")
    nxt = (f"Night {views[0].nid}", views[0].href) if views else None
    return page_shell(
        title=f"Where night falls — {title}",
        heading="Where night falls",
        body=body,
        kicker=kicker,
        kicker_href="index.html",
        night_ids=[v.nid for v in views],
        crumbs=[("Contents", "index.html"), ("Course", None)],
        meta_html=[esc(pace_line(nights)), esc(DEM_LIMITS_NOTE)],
        pager=(("Contents", "index.html"), nxt),
        spots_gpx=spots_gpx,
    )


def build_night(
    *,
    title: str,
    kicker: str,
    nv: NightView,
    views: list[NightView],
    sky: list[dict[str, Any]],
    plots: dict[str, str] | None,
    pager: tuple[tuple[str, str] | None, tuple[str, str] | None],
    spots_gpx: bool,
) -> str:
    body = [f"<p>{esc(night_window_text(nv.rec))}</p>"]
    if not nv.group:
        body.append("<p>No along-track samples in this window at predicted pace.</p>")
    else:
        if nv.featured is not None:
            rows = rows_for_sample(sky, int(nv.featured["i"]))
            body.append(f"<p class='lede'>{sky_lede(rows, nv)}</p>")
            body.extend(sample_disc_figures(nv.featured, plots))
            href = nv.stop_hrefs[int(nv.featured["i"])]
            body.append(
                "<p>Best-scored stop: "
                f'<a href="{esc(href)}">{esc(km_label(float(nv.featured["dist_km"])))}</a> · '
                f"{esc(fmt_time(nv.featured['time']))} · "
                f"{nv.featured['elev_m']:.0f} m.</p>"
            )
        if nv.ordered:
            body.append("<h3>Stargazing stops</h3>")
            body.append('<ul class="stops">')
            for s in nv.ordered:
                href = nv.stop_hrefs[int(s["i"])]
                body.append("  <li>")
                body.append(
                    f'    <a href="{esc(href)}">{esc(km_label(float(s["dist_km"])))} · '
                    f"{esc(fmt_time(s['time']))}</a>"
                )
                if nv.featured is not None and int(s["i"]) == int(nv.featured["i"]):
                    body.append("    <p class='meta'>best stop</p>")
                body.append(
                    f"    <p class='meta'>{sky_lede(rows_for_sample(sky, int(s['i'])), nv)}</p>"
                )
                body.append("  </li>")
            body.append("</ul>")
        body.append("<h3>This night</h3>")
        body.append("<ul>")
        body.append(
            f'  <li><a href="{esc(nv.sky_href)}">Planets and stars through the night</a></li>'
        )
        if nv.iau_href:
            noun = "constellation" if len(nv.iau_items) == 1 else "constellations"
            body.append(
                f'  <li><a href="{esc(nv.iau_href)}">'
                f"{len(nv.iau_items)} {noun} overhead or up at the stops</a></li>"
            )
        body.append("</ul>")
        other = same_place_html(views, nv.nid)
        if other:
            body.append(other)
        ref_names: list[str] = []
        for s in nv.ordered:
            ref_names.extend(sample_ref_names(rows_for_sample(sky, int(s["i"]))))
        body.extend(references_block(ref_names))
    return page_shell(
        title=f"Night {nv.nid} — {title}",
        heading=f"Night {nv.nid}",
        body=body,
        kicker=kicker,
        kicker_href="index.html",
        night_ids=[v.nid for v in views],
        crumbs=[("Contents", "index.html"), (f"Night {nv.nid}", None)],
        pager=pager,
        spots_gpx=spots_gpx,
    )


def build_stop(
    *,
    title: str,
    kicker: str,
    nv: NightView,
    views: list[NightView],
    sample: dict[str, Any],
    sky: list[dict[str, Any]],
    plots: dict[str, str] | None,
    pager: tuple[tuple[str, str] | None, tuple[str, str] | None],
    spots_gpx: bool,
) -> str:
    km = km_label(float(sample["dist_km"]))
    rows = rows_for_sample(sky, int(sample["i"]))
    body = [f"<p class='lede'>{sky_lede(rows, nv)}</p>"]
    body.extend(sample_disc_figures(sample, plots))
    body.extend(sample_sky_lists(rows, nv))
    more = [
        f'<a href="{esc(nv.href)}">Night {nv.nid}</a>',
        f'<a href="{esc(nv.sky_href)}">Planets and stars</a>',
    ]
    if nv.iau_href:
        more.append(f'<a href="{esc(nv.iau_href)}">Constellations this night</a>')
    body.append(f"<p class='meta'>{' · '.join(more)}</p>")
    others = [s for s in nv.ordered if int(s["i"]) != int(sample["i"])]
    if others:
        body.append("<h3>Other stops this night</h3>")
        body.append("<ul>")
        for s in others:
            href = nv.stop_hrefs[int(s["i"])]
            body.append(
                f'  <li><a href="{esc(href)}">{esc(km_label(float(s["dist_km"])))} · '
                f"{esc(fmt_time(s['time']))}</a></li>"
            )
        body.append("</ul>")
    other = same_place_html(views, nv.nid)
    if other:
        body.append(other)
    body.extend(references_block(sample_ref_names(rows)))
    return page_shell(
        title=f"{km} · Night {nv.nid} — {title}",
        heading=km,
        body=body,
        kicker=kicker,
        kicker_href="index.html",
        night_ids=[v.nid for v in views],
        crumbs=[
            ("Contents", "index.html"),
            (f"Night {nv.nid}", nv.href),
            (km, None),
        ],
        meta_html=[esc(sample_heading(sample))],
        pager=pager,
        spots_gpx=spots_gpx,
    )


def build_sky(
    *,
    title: str,
    kicker: str,
    nv: NightView,
    views: list[NightView],
    sky: list[dict[str, Any]],
    plots: dict[str, str] | None,
    spots_gpx: bool,
) -> str:
    body: list[str] = []
    body.extend(html_altitude_block(nv.nid, plots, "planets"))
    body.extend(html_altitude_block(nv.nid, plots, "stars"))
    if nv.featured is not None:
        rows = rows_for_sample(sky, int(nv.featured["i"]))
        href = nv.stop_hrefs[int(nv.featured["i"])]
        km = km_label(float(nv.featured["dist_km"]))
        body.append(
            f'<p>At the best stop (<a href="{esc(href)}">{esc(km)}</a>): '
            f"{sky_lede(rows, nv)}</p>"
        )
        body.append("<h4>Planets</h4>")
        body.extend(html_ul(planet_items(rows, nv), "none above the geometric horizon"))
    more = [f'<a href="{esc(nv.href)}">Night {nv.nid}</a>']
    if nv.iau_href:
        more.append(f'<a href="{esc(nv.iau_href)}">Constellations this night</a>')
    body.append(f"<p class='meta'>{' · '.join(more)}</p>")
    nxt = ("Constellations", nv.iau_href) if nv.iau_href else None
    return page_shell(
        title=f"Planets and stars · Night {nv.nid} — {title}",
        heading="Planets and stars",
        body=body,
        kicker=kicker,
        kicker_href="index.html",
        night_ids=[v.nid for v in views],
        crumbs=[
            ("Contents", "index.html"),
            (f"Night {nv.nid}", nv.href),
            ("Planets and stars", None),
        ],
        pager=((f"Night {nv.nid}", nv.href), nxt),
        spots_gpx=spots_gpx,
    )


def build_iau(
    *,
    title: str,
    kicker: str,
    nv: NightView,
    views: list[NightView],
    sky: list[dict[str, Any]],
    spots_gpx: bool,
) -> str:
    overhead: set[str] = set()
    up: set[str] = set()
    stop_names: list[tuple[dict[str, Any], set[str]]] = []
    for s in nv.ordered:
        groups = constellation_groups(rows_for_sample(sky, int(s["i"])))
        names = set(groups["overhead"]) | set(groups["up"])
        stop_names.append((s, names))
        overhead.update(groups["overhead"])
        up.update(groups["up"])
    up -= overhead
    body = [
        "<p class='meta'>Overhead or up at the stargazing stops. "
        "IAU plates from the course centroid, astronomical dusk to dawn.</p>",
    ]
    if overhead:
        body.append(
            f"<p class='jump'>Overhead: "
            f"{join_linked(sorted(overhead), nv)}.</p>"
        )
    if up:
        body.append(
            f"<p class='jump'>Up: {join_linked(sorted(up), nv)}.</p>"
        )
    others = other_nights(views, nv.nid)
    for plate_title, files in nv.iau_items:
        cid = constellation_id(plate_title)
        inner: list[str] = []
        for caption, src in files:
            inner.extend(
                html_src_figure(src, f"{plate_title} · {caption}", caption=caption)
            )
        here = [s for s, names in stop_names if name_in(plate_title, names)]
        if here:
            links = ", ".join(
                f'<a href="{esc(nv.stop_hrefs[int(s["i"])])}">'
                f"{esc(km_label(float(s['dist_km'])))}</a>"
                for s in here
            )
            inner.append(f"<p class='meta'>At {links}.</p>")
        for o in others:
            if cid in o.iau_ids and o.iau_href:
                inner.append(
                    f'<p class="meta"><a href="{esc(o.iau_href)}#{esc(cid)}">'
                    f"{esc(plate_title)} on Night {o.nid}</a></p>"
                )
        body.extend(
            html_details(
                titled_name(plate_title),
                inner,
                html_id=cid,
                css="iau-item",
                summary_html=True,
            )
        )
    return page_shell(
        title=f"Constellations · Night {nv.nid} — {title}",
        heading=(
            f"{len(nv.iau_items)} constellation this night"
            if len(nv.iau_items) == 1
            else f"{len(nv.iau_items)} constellations this night"
        ),
        body=body,
        kicker=kicker,
        kicker_href="index.html",
        night_ids=[v.nid for v in views],
        crumbs=[
            ("Contents", "index.html"),
            (f"Night {nv.nid}", nv.href),
            ("Constellations", None),
        ],
        pager=(
            ("Planets and stars", nv.sky_href),
            (f"Night {others[0].nid}", others[0].href) if others else (f"Night {nv.nid}", nv.href),
        ),
        spots_gpx=spots_gpx,
    )


def build_pages(
    cfg: dict[str, Any],
    nights: dict[str, Any],
    samples: list[dict[str, Any]],
    sky: list[dict[str, Any]],
    plots: dict[str, str] | None = None,
    iau_plots: dict[int, list[IauConstellation]] | None = None,
    spots: list[dict[str, Any]] | None = None,
    spots_gpx: bool = False,
) -> dict[str, str]:
    race = cfg.get("race") or {}
    title = race.get("name") or "Race"
    location = race.get("location") or ""
    kicker = f"{location} · {title}" if location else title
    night_list = list(nights.get("nights") or [])
    views = prepare_night_views(night_list, samples, sky, spots, iau_plots, plots)
    pages = {
        "index.html": build_index(
            title=title,
            kicker=kicker,
            tz=nights.get("timezone") or "local",
            views=views,
            sky=sky,
            spots_gpx=spots_gpx,
        ),
        "course.html": build_course(
            title=title,
            kicker=kicker,
            nights=nights,
            views=views,
            plots=plots,
            spots_gpx=spots_gpx,
            sample_m=sample_step_m(cfg),
        ),
    }
    for i, nv in enumerate(views):
        prev_n: tuple[str, str] | None = (
            ("Course", "course.html") if i == 0 else (f"Night {views[i - 1].nid}", views[i - 1].href)
        )
        next_n: tuple[str, str] | None = (
            (f"Night {views[i + 1].nid}", views[i + 1].href) if i + 1 < len(views) else None
        )
        pages[nv.href] = build_night(
            title=title,
            kicker=kicker,
            nv=nv,
            views=views,
            sky=sky,
            plots=plots,
            pager=(prev_n, next_n),
            spots_gpx=spots_gpx,
        )
        pages[nv.sky_href] = build_sky(
            title=title,
            kicker=kicker,
            nv=nv,
            views=views,
            sky=sky,
            plots=plots,
            spots_gpx=spots_gpx,
        )
        if nv.iau_href:
            pages[nv.iau_href] = build_iau(
                title=title,
                kicker=kicker,
                nv=nv,
                views=views,
                sky=sky,
                spots_gpx=spots_gpx,
            )
        for j, sample in enumerate(nv.ordered):
            prev_s: tuple[str, str] | None = (
                (f"Night {nv.nid}", nv.href)
                if j == 0
                else (
                    km_label(float(nv.ordered[j - 1]["dist_km"])),
                    nv.stop_hrefs[int(nv.ordered[j - 1]["i"])],
                )
            )
            if j + 1 < len(nv.ordered):
                next_s: tuple[str, str] | None = (
                    km_label(float(nv.ordered[j + 1]["dist_km"])),
                    nv.stop_hrefs[int(nv.ordered[j + 1]["i"])],
                )
            elif nv.iau_href:
                next_s = ("Constellations", nv.iau_href)
            else:
                next_s = ("Planets and stars", nv.sky_href)
            pages[nv.stop_hrefs[int(sample["i"])]] = build_stop(
                title=title,
                kicker=kicker,
                nv=nv,
                views=views,
                sample=sample,
                sky=sky,
                plots=plots,
                pager=(prev_s, next_s),
                spots_gpx=spots_gpx,
            )
    return pages


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
    spots_path = site_dir / "spots.json"
    spots = load_json(spots_path) if spots_path.is_file() else None
    site_dir.mkdir(parents=True, exist_ok=True)
    pages = build_pages(
        cfg,
        nights,
        samples,
        sky,
        plots=plot_links or None,
        iau_plots=iau_plot_gallery(site_dir) or None,
        spots=spots if isinstance(spots, list) else None,
        spots_gpx=(site_dir / "stargazing-spots.gpx").is_file(),
    )
    stale = [p for p in site_dir.glob("night-*.html") if p.name not in pages]
    course = site_dir / "course.html"
    if course.is_file() and "course.html" not in pages:
        stale.append(course)
    for p in stale:
        p.unlink()
    for name, text in pages.items():
        (site_dir / name).write_text(text, encoding="utf-8")
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
