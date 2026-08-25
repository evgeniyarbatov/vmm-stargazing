# CLAUDE.md

Guidance for working in this repository.

## What this is

Pre-computed night-sky notes for an ultra (planets, moon, constellations, terrain horizon) from a GPX + start/cutoff. Makefile is the pipeline; scripts under `scripts/` write files to `~/Documents/data/stargazing-ultras` (`DATA_DIR` / `DATA_ROOT` override).

Details: [docs/architecture.md](docs/architecture.md), [docs/usage.md](docs/usage.md). Keep README high-level.

## Commands

```sh
make install
make test
make run GPX=/path/to/course.gpx
make lint
```

Run scripts via `uv run python scripts/…` or Make. Python ≥ 3.11.

## Do not

- Commit DEM tiles, ephemeris, GPX, or generated tables.
- Call live Copernicus or download de421 from `make test`.
- Add a live planetarium or heavy star-catalogue rendering.
