# vmm-stargazing

Night sky along the VMM 100 — look up from the Hoàng Liên Sơn, make a memory, think bigger.

Pre-computed notes for Vietnam Mountain Marathon 100 Miles 2026 (Sa Pa): planets, moon, constellations, and DSM ridge vs stars at the **best stargazing places** on the course. Not a live planetarium.

**Notes:** [GitHub Pages](https://evgeniyarbatov.github.io/vmm-stargazing/)

**Waypoints:** [stargazing-spots.gpx](docs/stargazing-spots.gpx) — also a download on the site.

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
- Finish cutoff: Sunday 20 September 2026 ~09:00 (49 h). Predicted finishes are earlier (optimistic / realistic / conservative).
- Location: Sa Pa / Hoàng Liên Sơn, ~22.34° N, 103.84° E.

Race start, GPX path, and predicted-pace knobs live in `config.yaml`. The course GPX lives in `gpx/`. DEM caches and ephemeris stay out of git.

Along-track *time* uses the realistic predicted pace (when you reach a place). *Which* places are good for looking up is the best sample in each stretch of night (heading-open DSM sky, elevation on that night, moon, Milky Way centre) — not aid-station cutoffs.

## New course GPX

1. Put the file in `gpx/` and set `gpx:` in `config.yaml` to that path, **or** pass it once: `make run GPX=/path/to/course.gpx`.
2. Point `config.yaml` at the new event: `race.name`, `race.location`, `start_time`, `cutoff_time`, `timezone`. Replace `checkpoints.csv` if the course has published cutoffs.
3. If the track is in a new area: `make clean-dem`.
4. `make run`. First time on a new bbox downloads GLO-30; de421 is reused if already in `$DATA_DIR`. The site in `docs/` is generated from that run — do not edit the HTML by hand.
5. Commit `docs/` (including `stargazing-spots.gpx`) to update GitHub Pages.

`pace:` stays in `config.yaml` unless you have a new model. Knobs: [usage.md](usage.md).
