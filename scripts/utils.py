from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

EARTH_RADIUS_M = 6_371_000.0
EYE_M = 1.7
DEM_LIMITS_NOTE = (
    "Copernicus GLO-30 is a ~30 m DSM: major landforms only, not the trail surface."
)
LOOKAHEAD_M = 80.0


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def segment_lengths_m(lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    if len(lons) < 2:
        return np.zeros(0, dtype=float)
    out = np.empty(len(lons) - 1, dtype=float)
    for i in range(len(lons) - 1):
        out[i] = haversine_m(float(lons[i]), float(lats[i]), float(lons[i + 1]), float(lats[i + 1]))
    return out


def cumulative_m(lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    segs = segment_lengths_m(lons, lats)
    return np.concatenate([[0.0], np.cumsum(segs)])


def bearing_deg(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dlambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def destination_lonlat(lon: float, lat: float, bearing: float, dist_m: float) -> tuple[float, float]:
    ang = dist_m / EARTH_RADIUS_M
    br = math.radians(bearing)
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(ang) + math.cos(lat1) * math.sin(ang) * math.cos(br)
    )
    lon2 = lon1 + math.atan2(
        math.sin(br) * math.sin(ang) * math.cos(lat1),
        math.cos(ang) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lon2), math.degrees(lat2)


def densify_track(
    lons: np.ndarray,
    lats: np.ndarray,
    eles: np.ndarray,
    spacing_m: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if spacing_m <= 0:
        raise ValueError("spacing_m must be > 0")
    if len(lons) < 2:
        return np.asarray(lons, dtype=float), np.asarray(lats, dtype=float), np.asarray(eles, dtype=float)
    out_lon = [float(lons[0])]
    out_lat = [float(lats[0])]
    out_ele = [float(eles[0])]
    for i in range(len(lons) - 1):
        lon1, lat1, ele1 = float(lons[i]), float(lats[i]), float(eles[i])
        lon2, lat2, ele2 = float(lons[i + 1]), float(lats[i + 1]), float(eles[i + 1])
        dist = haversine_m(lon1, lat1, lon2, lat2)
        if dist < 1e-6:
            continue
        n_steps = max(1, int(round(dist / spacing_m)))
        for s in range(1, n_steps + 1):
            f = s / n_steps
            out_lon.append(lon1 + f * (lon2 - lon1))
            out_lat.append(lat1 + f * (lat2 - lat1))
            if np.isfinite(ele1) and np.isfinite(ele2):
                out_ele.append(ele1 + f * (ele2 - ele1))
            else:
                out_ele.append(ele2 if np.isfinite(ele2) else ele1)
    return np.asarray(out_lon, dtype=float), np.asarray(out_lat, dtype=float), np.asarray(out_ele, dtype=float)


def densify_lonlat(
    lons: np.ndarray,
    lats: np.ndarray,
    spacing_m: float,
) -> tuple[np.ndarray, np.ndarray]:
    eles = np.full(len(lons), np.nan, dtype=float)
    dlon, dlat, _ = densify_track(lons, lats, eles, spacing_m)
    return dlon, dlat


def sample_along(
    lons: np.ndarray,
    lats: np.ndarray,
    sample_m: float,
    eles: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if sample_m <= 0:
        raise ValueError("sample_m must be > 0")
    cum = cumulative_m(lons, lats)
    total = float(cum[-1])
    if total <= 0:
        raise ValueError("track length is zero")
    targets = list(np.arange(0.0, total, sample_m))
    if targets[-1] < total - 1.0:
        targets.append(total)
    dist = np.asarray(targets, dtype=float)
    lon = np.interp(dist, cum, lons)
    lat = np.interp(dist, cum, lats)
    ele = np.full(len(dist), np.nan, dtype=float) if eles is None else np.interp(dist, cum, eles)
    return lon, lat, dist, ele


def interp_at(
    lons: np.ndarray,
    lats: np.ndarray,
    dist_m: float,
) -> tuple[float, float]:
    cum = cumulative_m(lons, lats)
    d = min(max(dist_m, 0.0), float(cum[-1]))
    return float(np.interp(d, cum, lons)), float(np.interp(d, cum, lats))


def heading_at(
    lons: np.ndarray,
    lats: np.ndarray,
    dist_m: float,
    lookahead_m: float,
    total_m: float,
) -> float:
    if total_m <= 0:
        return 0.0
    ahead = min(dist_m + lookahead_m, total_m)
    if ahead - dist_m < 1.0:
        behind = max(dist_m - lookahead_m, 0.0)
        lon1, lat1 = interp_at(lons, lats, behind)
        lon2, lat2 = interp_at(lons, lats, dist_m)
    else:
        lon1, lat1 = interp_at(lons, lats, dist_m)
        lon2, lat2 = interp_at(lons, lats, ahead)
    return bearing_deg(lon1, lat1, lon2, lat2)


def bbox_of(lons: np.ndarray, lats: np.ndarray) -> dict[str, float]:
    return {
        "west": float(np.min(lons)),
        "south": float(np.min(lats)),
        "east": float(np.max(lons)),
        "north": float(np.max(lats)),
    }


def expand_bbox(bbox: dict[str, float], buffer_km: float) -> dict[str, float]:
    if buffer_km < 0:
        raise ValueError("buffer_km must be >= 0")
    mean_lat = (bbox["south"] + bbox["north"]) / 2.0
    lat_deg = buffer_km / 111.32
    cos_lat = math.cos(math.radians(mean_lat))
    lon_deg = buffer_km / (111.32 * max(cos_lat, 0.1))
    return {
        "west": bbox["west"] - lon_deg,
        "south": bbox["south"] - lat_deg,
        "east": bbox["east"] + lon_deg,
        "north": bbox["north"] + lat_deg,
    }


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def dump_json(path: Path, payload: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2, default=json_default) + "\n", encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def compass8(az_deg: float) -> str:
    names = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    return names[int((az_deg + 22.5) % 360.0 // 45.0)]


def lerp_wrap_deg(values: np.ndarray, az_deg: float) -> float:
    n = len(values)
    if n == 0:
        return 0.0
    step = 360.0 / n
    x = az_deg % 360.0
    i0 = int(x // step) % n
    i1 = (i0 + 1) % n
    f = (x - i0 * step) / step
    return float(values[i0] * (1.0 - f) + values[i1] * f)
