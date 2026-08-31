# CLAUDE.md

Guidance for working in this repository.

## What this is

Pre-computed night-sky notes for VMM 100 Miles 2026 (planets, moon, constellations, terrain horizon) from a GPX + start/cutoff. Makefile is the pipeline; scripts under `scripts/` write cache to `~/Documents/data/vmm-stargazing` (`DATA_DIR` / `DATA_ROOT` override) and the public site to `docs/`.

Details: [architecture.md](architecture.md), [usage.md](usage.md). Keep README high-level.

## Commands

```sh
make install
make test
make run
make plots
make site
make lint
```

Run scripts via `uv run python scripts/…` or Make. Python ≥ 3.11.

## Do not

- Commit DEM tiles, ephemeris, or `$DATA_DIR` cache.
- Call live Copernicus or download de421 from `make test`.
- Add a live planetarium or heavy star-catalogue rendering.
