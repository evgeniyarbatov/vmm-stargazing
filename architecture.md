# Architecture

Makefile is the pipeline DAG. Each stage is a script under `scripts/` that reads and writes files under `~/Documents/data/vmm-stargazing` (`DATA_DIR` / `DATA_ROOT` override). Scripts do not call each other except shared helpers.

```text
config.yaml + GPX
  → gpx.py       copy into DATA_DIR, densify track, write bbox
  → dem.py       Copernicus GLO-30 GeoTIFF for bbox + buffer (cached)
  → timeline.py  astronomical night windows + along-track samples
  → sky.py       planets / moon / stars + DEM horizon at each sample
  → plots.py     course map, sky discs, altitude, spots → docs/plots/
  → constellations.py  clone IAU plots for each night → docs/plots/constellations/
  → report.py    GitHub Pages HTML + data.json → docs/
```

`make run` is that chain (`GPX=…` overrides the in-repo course). Later stages can be re-run alone if their inputs still exist. `make plots` rebuilds PNGs from existing `samples.json` / `sky.json` / DEM.

## Layout

Repo `gpx/` holds the committed course file. The pipeline copies it into `$DATA_DIR` and densifies from there.

```text
$DATA_DIR/
  gpx/<config name>.gpx   working copy of the repo GPX
  input.gpx               densified track
  bbox.json               tight lon/lat envelope + length
  dem/glo30.tif           cached GLO-30 (orthometric)
  ephemeris/de421.bsp     Skyfield JPL kernel (downloaded once)
  nights.json             twilight intervals + night windows
  samples.json            observer states during nights
  sky.json                bodies at each sample

docs/                     GitHub Pages (committed)
  index.html
  style.css
  data.json               nights + samples + sky (download)
  plots/course.png
  plots/profile.png
  plots/spots.png
  plots/nightN-sI.png
  plots/nightN-sI-ahead.png
  plots/nightN-alt-planets.png
  plots/nightN-alt-stars.png
  plots/constellations/nightN/*.png
```

`$DATA_DIR` is not committed (DEM, ephemeris, and the cloned `constellations` checkout included). The site in `docs/` is, including IAU constellation PNGs. Tests use a tiny synthetic ridge; they never download Copernicus, de421, or clone constellations.

## Time model

GPX timestamps from mapping tools are ignored. Along-track time uses the optimistic / realistic / conservative pace model (climb, descent, fatigue that accrues with absolute km, plus stoppage), calibrated on a VMM 100 K. Maps and samples use the realistic scenario. Night windows are true night (Sun altitude < −18°) at the course centroid. Samples exist only inside those windows, every `sampling.distance_m`, capped per night.

Planet alt/az barely change across this course. Terrain horizon does.

## DEM

`dem-stitcher` pulls Copernicus GLO-30 from the public AWS registry (no API key). Heights are orthometric. The bbox is padded by `BUFFER_KM` (default 15 km) so horizon rays have terrain to look at.

If `dem/glo30.tif` already exists and is non-empty, fetch is skipped. `make test` never calls the stitcher.

GLO-30 is a ~30 m **DSM**: trees and buildings are in the surface. Horizon masking is topographic context, not trail-level.

## Sky

Skyfield + de421. Classical planets Mercury–Saturn, Moon phase/illumination, a bright-star catalog for constellation presence, and the galactic centre as a Milky Way marker. A body is terrain-obscured if its altitude is below the DEM horizon in that azimuth plus `visibility.horizon_buffer_deg`.
