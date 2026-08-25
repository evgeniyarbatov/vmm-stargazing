from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from catalog import PLANETS, STARS, SkyTarget

TWILIGHT_CODES = {
    0: "night",
    1: "astronomical_twilight",
    2: "nautical_twilight",
    3: "civil_twilight",
    4: "day",
}

TWILIGHT_TRANSITIONS = {
    (4, 3): "sunset",
    (3, 2): "civil_dusk",
    (2, 1): "nautical_dusk",
    (1, 0): "astronomical_dusk",
    (0, 1): "astronomical_dawn",
    (1, 2): "nautical_dawn",
    (2, 3): "civil_dawn",
    (3, 4): "sunrise",
}


def load_ephemeris(cache_dir: Path) -> tuple[Any, Any]:
    from skyfield.api import Loader

    cache_dir.mkdir(parents=True, exist_ok=True)
    loader = Loader(str(cache_dir))
    return loader.timescale(), loader("de421.bsp")


def intervals_from_codes(
    t_start: datetime,
    code0: int,
    trans_times: list[datetime],
    trans_codes: list[int],
    t_end: datetime,
) -> list[dict[str, Any]]:
    points: list[tuple[datetime, int]] = [(t_start, code0)]
    for t, code in zip(trans_times, trans_codes, strict=True):
        if t_start < t < t_end:
            points.append((t, code))
    intervals: list[dict[str, Any]] = []
    for i, (t, code) in enumerate(points):
        end = points[i + 1][0] if i + 1 < len(points) else t_end
        if end <= t:
            continue
        intervals.append(
            {
                "start": t,
                "end": end,
                "code": int(code),
                "label": TWILIGHT_CODES.get(int(code), str(code)),
            }
        )
    return intervals


def transition_events(intervals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for i in range(len(intervals) - 1):
        a = intervals[i]
        b = intervals[i + 1]
        name = TWILIGHT_TRANSITIONS.get((a["code"], b["code"]))
        if name is None:
            continue
        events.append({"time": b["start"], "event": name, "from": a["label"], "to": b["label"]})
    return events


def night_windows(intervals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nights = [row for row in intervals if row["code"] == 0]
    out: list[dict[str, Any]] = []
    for i, row in enumerate(nights, start=1):
        out.append({**row, "night_id": i})
    return out


def twilight_intervals(
    ts: Any,
    eph: Any,
    lat: float,
    lon: float,
    elev_m: float,
    t_start: datetime,
    t_end: datetime,
) -> list[dict[str, Any]]:
    from skyfield import almanac
    from skyfield.api import wgs84

    loc = wgs84.latlon(lat, lon, elevation_m=elev_m)
    fn = almanac.dark_twilight_day(eph, loc)
    t0 = ts.from_datetime(t_start)
    t1 = ts.from_datetime(t_end)
    times, events = almanac.find_discrete(t0, t1, fn)
    code0 = int(np_item(fn(t0)))
    tz = t_start.tzinfo
    trans_times = [times[i].utc_datetime().astimezone(tz) for i in range(len(times))]
    trans_codes = [int(events[i]) for i in range(len(events))]
    return intervals_from_codes(t_start, code0, trans_times, trans_codes, t_end)


def np_item(value: Any) -> Any:
    return value.item() if hasattr(value, "item") else value


def observer_at(eph: Any, lat: float, lon: float, elev_m: float) -> Any:
    from skyfield.api import wgs84

    return eph["earth"] + wgs84.latlon(lat, lon, elevation_m=elev_m)


def altaz_of(app: Any) -> tuple[float, float]:
    alt, az, _dist = app.altaz()
    return float(alt.degrees), float(az.degrees)


def observe_planet(
    ts: Any,
    eph: Any,
    lat: float,
    lon: float,
    elev_m: float,
    when: datetime,
    name: str,
    target: str,
) -> dict[str, Any]:
    t = ts.from_datetime(when)
    app = observer_at(eph, lat, lon, elev_m).at(t).observe(eph[target]).apparent()
    alt, az = altaz_of(app)
    mag: float | None
    try:
        from skyfield.magnitudelib import planetary_magnitude

        mag = float(planetary_magnitude(app))
    except (ValueError, TypeError, AttributeError):
        mag = None
    return {
        "kind": "planet",
        "name": name,
        "alt_deg": alt,
        "az_deg": az,
        "mag": mag,
        "constellation": "",
    }


def observe_star(
    ts: Any,
    eph: Any,
    lat: float,
    lon: float,
    elev_m: float,
    when: datetime,
    star: SkyTarget,
) -> dict[str, Any]:
    from skyfield.api import Star

    t = ts.from_datetime(when)
    body = Star(ra_hours=star.ra_hours, dec_degrees=star.dec_deg)
    app = observer_at(eph, lat, lon, elev_m).at(t).observe(body).apparent()
    alt, az = altaz_of(app)
    return {
        "kind": star.kind,
        "name": star.name,
        "alt_deg": alt,
        "az_deg": az,
        "mag": star.mag,
        "constellation": star.constellation,
    }


def observe_moon(
    ts: Any,
    eph: Any,
    lat: float,
    lon: float,
    elev_m: float,
    when: datetime,
) -> dict[str, Any]:
    from skyfield import almanac

    t = ts.from_datetime(when)
    app = observer_at(eph, lat, lon, elev_m).at(t).observe(eph["moon"]).apparent()
    alt, az = altaz_of(app)
    illum = float(almanac.fraction_illuminated(eph, "moon", t))
    phase = float(almanac.moon_phase(eph, t).degrees)
    return {
        "kind": "moon",
        "name": "Moon",
        "alt_deg": alt,
        "az_deg": az,
        "mag": None,
        "constellation": "",
        "illumination": illum,
        "phase_deg": phase,
        "phase_name": moon_phase_name(phase),
    }


def moon_phase_name(phase_deg: float) -> str:
    p = phase_deg % 360.0
    if p < 22.5 or p >= 337.5:
        return "new"
    if p < 67.5:
        return "waxing crescent"
    if p < 112.5:
        return "first quarter"
    if p < 157.5:
        return "waxing gibbous"
    if p < 202.5:
        return "full"
    if p < 247.5:
        return "waning gibbous"
    if p < 292.5:
        return "last quarter"
    return "waning crescent"


def observe_all(
    ts: Any,
    eph: Any,
    lat: float,
    lon: float,
    elev_m: float,
    when: datetime,
    include_moon: bool,
    include_milky_way: bool,
) -> list[dict[str, Any]]:
    from catalog import GALACTIC_CENTER

    rows = [
        observe_planet(ts, eph, lat, lon, elev_m, when, name, target) for name, target in PLANETS
    ]
    if include_moon:
        rows.append(observe_moon(ts, eph, lat, lon, elev_m, when))
    rows.extend(observe_star(ts, eph, lat, lon, elev_m, when, star) for star in STARS)
    if include_milky_way:
        rows.append(observe_star(ts, eph, lat, lon, elev_m, when, GALACTIC_CENTER))
    return rows
