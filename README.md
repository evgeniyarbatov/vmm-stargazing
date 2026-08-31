# vmm-stargazing

Night sky along the VMM 100 — look up from the Hoàng Liên Sơn, make a memory, think bigger.

Pre-computed notes for Vietnam Mountain Marathon 100 Miles 2026 (Sa Pa): planets, moon, constellations, and the terrain horizon from the GPX + start/cutoff. Not a live planetarium.

**Notes:** [GitHub Pages](https://evgeniyarbatov.github.io/vmm-stargazing/)

## Quick start

```bash
make install
make test
make run
```

`make run` writes the public site into `docs/`. First run downloads Copernicus GLO-30 and the de421 ephemeris into `~/Documents/data/vmm-stargazing` (`DATA_DIR` / `DATA_ROOT` override).

See [usage.md](usage.md) for knobs and [architecture.md](architecture.md) for how the stages connect. Where this is going: [ROADMAP.md](ROADMAP.md).

## Race

- Distance: ~161 km, ~8800 m elevation gain.
- Start: Friday 18 September 2026, 08:00 local (Asia/Ho_Chi_Minh, UTC+7) at Sapa Square.
- Approximate finish cutoff: Sunday 20 September 2026 ~09:00 (49 h time limit).
- Location: Sa Pa / Hoàng Liên Sơn, ~22.34° N, 103.84° E.

Race parameters live in `config.yaml`. The course GPX lives in-repo (`gpx/`). Predicted pace (optimistic / realistic / conservative) lives under `pace:` in that config. DEM caches and ephemeris stay out of git.

Along-track times follow the realistic predicted pace. Faster running shifts night locations earlier on the course; planet positions barely change across this bbox.
