# Usage

```bash
make install
make test
make run
```

Python ≥ 3.11, `uv` on `PATH`. `make test` is offline (synthetic GPX + GeoTIFF). The first `make dem` downloads GLO-30; the first `make timeline` downloads de421 into `$DATA_DIR/ephemeris/`.

How the stages fit together: [architecture.md](architecture.md).

## Output

Default cache: `~/Documents/data/vmm-stargazing/`. The public site is `docs/` in the repo.

| Override | Effect |
|---|---|
| `DATA_ROOT=/other/root` | files under `/other/root/vmm-stargazing/` |
| `DATA_DIR=/exact/path` | files under that path |
| `SITE_DIR=/exact/path` | GitHub Pages files under that path |

`docs/index.html` embeds PNGs from `docs/plots/`. Raw data is `docs/data.json`; each chart has a download link on the page.

`make clean` removes nights/samples/sky (keeps DEM + ephemeris + `docs/`). `make clean-dem` drops the GeoTIFF.

## What to re-run

| Changed | Re-run |
|---|---|
| GPX file | `make run` (or `make run GPX=…` to override) |
| `BUFFER_KM` | `make clean-dem dem timeline sky plots site` |
| start/cutoff in `config.yaml` | `make timeline sky plots site` |
| sampling / magnitude / horizon buffer | `make timeline sky plots site` |

## Knobs

| Knob | Default | Meaning |
|---|---|---|
| `DENSIFY_M` | 10 | Polyline spacing after GPX clean (m) |
| `BUFFER_KM` | 15 | DEM pad around the track bbox (km) |
| `SAMPLE_M` | from config (2000) | Along-track spacing during night (m) |

Race timing, magnitude limit, and horizon buffer live in `config.yaml`.

Copernicus GLO-30 is a ~30 m DSM. It shows ridges and valleys — not the trail tread.
