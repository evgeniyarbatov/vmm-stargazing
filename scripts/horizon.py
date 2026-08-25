from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import rasterio
from dem import sample_elev_xy
from utils import EYE_M, destination_lonlat, lerp_wrap_deg


def load_dem_array(path: Path) -> tuple[np.ndarray, object, float | None]:
    with rasterio.open(path) as dem:
        return dem.read(1), dem.transform, dem.nodata


def horizon_profile(
    array: np.ndarray,
    transform: object,
    lon: float,
    lat: float,
    elev_m: float,
    n_az: int = 36,
    max_km: float = 15.0,
    step_m: float = 200.0,
    eye_m: float = EYE_M,
) -> np.ndarray:
    eye = elev_m + eye_m
    n_steps = max(1, int(max_km * 1000.0 / step_m))
    profile = np.zeros(n_az, dtype=float)
    for i in range(n_az):
        az = i * (360.0 / n_az)
        max_alt = 0.0
        for s in range(1, n_steps + 1):
            dist = s * step_m
            dlon, dlat = destination_lonlat(lon, lat, az, dist)
            z = sample_elev_xy(array, transform, dlon, dlat, None)
            if not np.isfinite(z):
                continue
            alt = math.degrees(math.atan2(z - eye, dist))
            if alt > max_alt:
                max_alt = alt
        profile[i] = max_alt
    return profile


def horizon_at_az(profile: np.ndarray, az_deg: float) -> float:
    return lerp_wrap_deg(profile, az_deg)
