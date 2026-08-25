# stargazing-ultras

Understand what is visible in the night sky while running an ultra, given a GPX course, start time, and cutoff.

Primary target: VMM 100 Miles 2026 (Sapa, Vietnam) — long night sections under dark mountain skies if weather cooperates.

This is **not** a live planetarium. It is pre-computation + lightweight lookup material for a multi-night ultra.

## Quick start

```bash
make install
make test
make run
```

Night summaries land in `~/Documents/data/stargazing-ultras/out/summary.md` (`DATA_DIR` / `DATA_ROOT` override). First run downloads Copernicus GLO-30 and the de421 ephemeris into that data dir.

See [docs/usage.md](docs/usage.md) for knobs and [docs/architecture.md](docs/architecture.md) for how the stages connect.

## Goal

Given a race configuration (GPX + start + cutoff):

1. Exact windows of true night (astronomical dusk → astronomical dawn) along the course timeline.
2. For positions/times during those windows: planets above the local horizon (alt/az + magnitude), major constellations (rising / setting / overhead), Moon phase, Milky Way centre if computable.
3. Observer elevation and a simple DEM horizon so low objects behind ridges can be flagged.
4. Offline-friendly markdown + CSV for phone review or pre-race study.

## Race context (VMM 100 Miles 2026)

- Distance: ~161 km, ~8800 m elevation gain.
- Start: Friday 18 September 2026, 08:00 local (Asia/Ho_Chi_Minh, UTC+7) at Sapa Square.
- Approximate finish cutoff: Sunday 20 September 2026 ~09:00 (49 h time limit).
- Location: Sa Pa / Hoàng Liên Sơn, ~22.34° N, 103.84° E.

## Config

All race-specific parameters live in `config.yaml`.

The course GPX lives in-repo (`gpx/`). DEM caches, ephemeris, and generated tables live under `~/Documents/data/stargazing-ultras`.

Along-track times assume even pace to the cutoff. Faster running shifts night locations earlier on the course; planet positions barely change across this bbox.

## Pipeline

```text
GPX + config → densify / bbox
             → Copernicus GLO-30 cache
             → astronomical night windows + night-only samples
             → planets / moon / stars + DEM horizon
             → course map, sky discs, altitude charts
             → markdown + CSV
```

Makefile-driven, `uv` + `pyproject.toml`, small scripts. DEM fetch matches `gpx-dem-preview` (`dem-stitcher`, GLO-30, data outside the repo). Ephemeris via `skyfield` + de421.

GLO-30 is a ~30 m DSM: ridges and valleys, not the trail.

## Status

Pipeline is in: `make run` writes night windows, planet/constellation tables, sky discs along the GPX, and a short summary. No live app.
