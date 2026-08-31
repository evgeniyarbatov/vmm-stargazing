# CLAUDE.md

Guidance for working in this repository.

## What this is

Pre-computed night-sky notes from a GPX + start/cutoff (planets, moon, constellations, terrain horizon). Makefile is the pipeline; scripts under `scripts/` write cache to `~/Documents/data/vmm-stargazing` (`DATA_DIR` / `DATA_ROOT` override) and a multi-page GitHub Pages site to `docs/` (`report.py`).

Details: [architecture.md](architecture.md), [usage.md](usage.md). Keep README high-level. New course: README "New course GPX".

## Commands

```sh
make install
make test
make run
make plots
make constellations
make site
make lint
```

Run scripts via `uv run python scripts/…` or Make. Python ≥ 3.11.

## Do not

- Commit DEM tiles, ephemeris, `$DATA_DIR` cache, or the cloned constellations checkout.
- Call live Copernicus, download de421, or clone constellations from `make test`.
- Add a live planetarium or heavy star-catalogue rendering.
- Edit `docs/*.html` by hand — `make site` / `make run` regenerates it.
- Hardcode course facts (night count, place names, kilometre spans) into `report.py` copy; derive them from the GPX, `nights.json`, and `config.yaml`.
