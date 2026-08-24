# stargazing-ultras

Understand what is visible in the night sky while running an ultra, given a GPX course, start time, and cutoff.

Primary target: VMM 100 Miles 2026 (Sapa, Vietnam) — long night sections under dark mountain skies if weather cooperates.

**Prompt-only bootstrap.** No implementation code yet. This README is the standing instruction set for any future agent or coding session.

## Goal

Given a race configuration (GPX + start + cutoff):

1. Determine the exact windows of true night (astronomical dusk → astronomical dawn) along the course timeline.
2. For positions/times during those windows, report:
   - Which planets are above the local horizon and roughly where (azimuth / altitude).
   - Which major constellations are visible (and which are rising / setting / overhead).
   - Optional: bright stars, Moon phase & position if relevant, Milky Way orientation if computable.
3. Account for observer elevation and local terrain (via DEM) so horizon masking is realistic in steep mountain terrain.
4. Produce offline-friendly reference material (tables, short annotated sky notes, maybe simple polar plots or text summaries) usable on a phone during the race or for pre-race study.

This is **not** a live planetarium app. It is pre-computation + lightweight lookup material for a multi-night ultra.

## Race context (VMM 100 Miles 2026)

- Distance: ~161 km, ~8800 m elevation gain.
- Start: Friday 18 September 2026, 08:00 local (Asia/Ho_Chi_Minh, UTC+7) at Sapa Square.
- Approximate finish cutoff: Sunday 20 September 2026 ~09:00 (49 h time limit).
- Location: Sa Pa / Hoàng Liên Sơn, ~22.34° N, 103.84° E. Town elevation ~1 500–1 600 m; course climbs substantially higher.
- Expected nights: Friday night into Saturday, Saturday night into Sunday.

Exact GPX will be supplied via config; until then treat Sapa town + typical VMM corridor as the bounding box.

## Config

All race-specific parameters live in `config.yaml` (see that file).

Minimum fields:

- `gpx`: path (or data-dir relative path) to the course GPX.
- `start_time`: ISO 8601 with timezone (or local + explicit timezone).
- `cutoff_time` or `time_limit_hours`.
- Optional: `timezone`, default observer lat/lon/elev, DEM source preference, sampling interval along track, magnitude limits, etc.

Data (GPX, DEM caches, generated sky tables) lives **outside** the repo under `~/data/stargazing-ultras` (or `DATA_DIR` / `DATA_ROOT` overrides). Nothing heavy is committed.

## Required capabilities (what the system must eventually do)

### 1. Timeline of darkness

- Compute astronomical dusk and astronomical dawn (Sun altitude = −18°) for the relevant dates at the course latitude/longitude (and preferably at sampled elevations).
- Also report civil and nautical twilight for context.
- Produce a clear table of night windows relative to race elapsed time / clock time.

Prefer `skyfield` (almanac / dark_twilight_day) or equivalent accurate library. `astral` is acceptable for sun/moon rise-set but skyfield is preferred for consistency with planet positions.

### 2. Observer state along the GPX

- Parse / clean / densify the GPX (reuse patterns from `gpx-courses`, `minimal-gpx`, `anonymize-gpx`).
- Sample at configurable distance or time intervals during night windows only.
- For each sample: lat, lon, elevation (from GPX if present, else from DEM), heading, race elapsed time, local solar time.

### 3. DEM for elevation & horizon

- Fetch / cache Copernicus GLO-30 (or equivalent free global DEM) for the course bounding box — same approach as `gpx-dem-preview` and `3d-gpx-track`.
- Use DEM both for:
  - Filling missing elevations.
  - Optional simple horizon profile (azimuthal max elevation angle) so low planets/constellations behind ridges can be flagged as “likely obscured”.
- Document 30 m resolution limits; this is topographic context, not trail-level precision.

### 4. Planets

- For each night sample (or a few representative times per night): compute apparent altitude/azimuth of the classical planets (Mercury–Saturn) + any bright outer ones of interest.
- Flag which are above the local (terrain-adjusted) horizon and brighter than a magnitude threshold.
- Note conjunctions, close approaches, or especially prominent planets (e.g. bright Venus or Jupiter).

Use `skyfield` + JPL ephemeris (de421 or newer).

### 5. Constellations & bright sky features

- Determine which major constellations are above the horizon (or rising/setting) at sample times.
- Prefer a lightweight constellation boundary / stick-figure dataset rather than full star catalogues if possible.
- Optionally list a handful of navigational bright stars (Sirius, Canopus, Vega, etc.) with alt/az.
- Moon: phase, illumination, altitude — important because a bright Moon washes out the Milky Way and faint constellations.

### 6. Output style

- Human-readable night-by-night summaries (“Friday night after ~19:40 local until ~04:50 Saturday: …”).
- Compact tables keyed by race elapsed time or distance.
- Optional simple text or SVG polar sky plots for key moments (midnight, etc.).
- Everything offline-friendly for phone review before / during the race.

## Reuse existing work (do not reinvent)

- **GPX handling & pipelines**: `evgeniyarbatov/gpx-courses`, `minimal-gpx`, `gpx-map`, `anonymize-gpx`, Makefile-first style from `gnss` / `gpx-dem-preview`.
- **DEM fetch & terrain**: `gpx-dem-preview` (Copernicus 30 m, data outside repo), `3d-gpx-track`.
- **Solar / time-of-day along GPX**: `edge-gpx` (already computes solar position + pace + time for color sequences).
- **General geospatial / data-dir conventions**: same `~/data/...` + `DATA_DIR` pattern used across the personal geospatial repos.
- **Config style**: simple YAML like `edge-gpx/config.yaml`.

Keep the same pragmatic constraints: Makefile targets, `uv` + `pyproject.toml`, small scripts, private until useful.

## Bootstrap prompt for agents / future work

Use the following as the standing instruction when adding any code or expanding the repo:

> Extend `stargazing-ultras` following the conventions of `evgeniyarbatov/gpx-dem-preview`, `evgeniyarbatov/edge-gpx`, and `evgeniyarbatov/gpx-courses`:
>
> - Makefile-driven, data under `~/data/stargazing-ultras` (overridable via `DATA_DIR` / `DATA_ROOT`).
> - `pyproject.toml` + uv; scripts small and single-purpose.
> - Config-driven via `config.yaml` (GPX path, start_time, cutoff_time / time_limit, timezone, optional magnitude limits, sampling).
> - First useful deliverable: for a given GPX + start/cutoff,
>   1. exact astronomical dusk/dawn windows for the race nights at Sapa latitude,
>   2. list of planets above the horizon (alt/az + magnitude) at a few key times per night,
>   3. major constellations visible during those windows,
>   4. brief human-readable summary suitable for pre-race study.
> - Reuse DEM caching approach from `gpx-dem-preview` so observer elevation and simple horizon masking are available.
> - Prefer `skyfield` for ephemeris, twilight, and planet positions.
> - No real-time app, no heavy star-catalogue rendering in v1; tables + short notes are enough.
> - Keep the repo private until the pipeline produces something actually useful on race day.

## Status

Private bootstrap only. Prompt and config skeleton present. No code yet.

Next step once a Sapa 100-mile GPX is available: implement the darkness timeline + planet visibility table first; constellation and DEM horizon second.
