# Usage

```bash
make install
make test
make run GPX=~/Downloads/vietnam-mountain-marathon-2024-ultra-100-miles.gpx
```

Python ≥ 3.11, `uv` on `PATH`. `make test` is offline (synthetic GPX + GeoTIFF). The first `make dem` downloads GLO-30; the first `make timeline` downloads de421 into `$DATA_DIR/ephemeris/`.

How the stages fit together: [architecture.md](architecture.md).

## Output

Default root: `~/Documents/data/stargazing-ultras/`.

| Override | Effect |
|---|---|
| `DATA_ROOT=/other/root` | files under `/other/root/stargazing-ultras/` |
| `DATA_DIR=/exact/path` | files under that path |

Human-readable notes: `$DATA_DIR/out/summary.md`. Tables: `nights.csv`, `samples.csv`, `sky.csv`.

`make clean` removes nights/samples/sky/out (keeps DEM + ephemeris). `make clean-dem` drops the GeoTIFF.

## What to re-run

| Changed | Re-run |
|---|---|
| GPX file | `make run GPX=…` |
| `BUFFER_KM` | `make clean-dem dem timeline sky report` |
| start/cutoff in `config.yaml` | `make timeline sky report` |
| sampling / magnitude / horizon buffer | `make timeline sky report` |

## Knobs

| Knob | Default | Meaning |
|---|---|---|
| `DENSIFY_M` | 10 | Polyline spacing after GPX clean (m) |
| `BUFFER_KM` | 15 | DEM pad around the track bbox (km) |
| `SAMPLE_M` | from config (2000) | Along-track spacing during night (m) |

Race timing, magnitude limit, and horizon buffer live in `config.yaml`.

Copernicus GLO-30 is a ~30 m DSM. It shows ridges and valleys — not the trail tread.
