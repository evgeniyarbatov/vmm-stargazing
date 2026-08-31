# Roadmap

Two jobs: make someone curious enough to look up, and leave them with a constellation tied to a ridge. The end of that is thinking bigger. VMM 2026 is the place that happens — not a generic ultra tool.

The site is a precomputed field notebook (`docs/`, PNGs + HTML). It is not a planetarium.

## Already in the notebook

Checkpoint-cutoff pace along the GPX (`checkpoints.csv` → `timeline.py`), with optimistic / realistic / conservative finishes. Maps and samples use realistic. True night windows at the course centroid. Along-track samples only in those windows.

At each sample: planets Mercury–Saturn, Moon phase, ~60 named stars with a constellation label, Milky Way centre, GLO-30 DSM horizon (`sky.json`). A gold-ringed nav star is the one in the heading cone.

A multi-page notebook: contents, course (pace table + map + profile + twilight), one page per night, one page per scored stop, planet/star altitude, IAU plates. Copy is derived from the GPX, `nights.json`, and `config.yaml`.

Stops are scored from open DSM horizon, elevation, moon wash, and whether the Milky Way centre clears the ridge. A few per night, spaced. Each has a sky disc and a DSM look-ahead facing the GPX. Waypoints go out as `stargazing-spots.gpx`. On the current page that is four places on Night 1 and two on Night 2.

Altitude charts are one plot per planet, the moon, and each bright star that comes above 5°. IAU plates (chart / azimuth / altitude) cover constellations overhead or up at the stops. Nights cross-link as “same sky, different place”. `data.json` is the raw dump.

Constellation “presence” is: at least one catalogued star from that constellation is up. Discs and look-aheads draw a nav-star subset, not stick figures.

What the pages still do not do: name a stop after what you would look at, put a “look at this” line under a picture, call Vega–Altair–Deneb a triangle, or read Night 1’s four stops as one turning sky.

## Hard limits

GLO-30 is a ~30 m DSM with 15 km rays. Ridges and valleys, not the tread. Horizon masking is topographic context.

Planet alt/az barely move across this bbox. Where you stand, and the ridge in front of you, do.

Samples are discrete (about 2 km, capped per night). There is no interpolation of the sky between them.

IAU plates are from the course centroid, dusk to dawn — not the heading from a stop. A plate is a finding chart, not what the look-ahead shows.

GitHub Pages cannot store “what I saw”. No form, no database.

`make test` stays offline. No live Copernicus, no live planetarium, no Hipparcos / constellation-line catalogue.

## Do next

Work in this order. Each item is one change to the existing pipeline, then `make plots site`.

### 1. Name the stops

Stops are `km 62`, `km 84`, and so on. The GPX waypoints are `Night 1 · km 62`. The night `<h1>` is still a number. The look-ahead already knows the ahead star; the lede already knows the overhead constellations.

Pick a name from data already on that sample: the star marked ahead, or the overhead constellation if nothing is in the heading cone. Use it on the spots map, the look-ahead title, the stop `<h1>`, and the waypoint. Keep the kilometre as the subtitle.

Done when Night 1’s best stop is something like “Deneb, km 62” in the notebook and in the GPX, not a score.

### 2. One notice line under each picture

`report.py` already writes a moon sentence, a Milky Way sentence, and a dumped constellation list. The page lede concatenates those. Each disc and look-ahead has no “if you stop, look at this”.

Add one function that returns a single sentence from the sample + `sky.json` row: the ahead star against the DSM, or Moon wash, or Milky Way centre if it is up. Put it under the look-ahead and under the disc. Do not add a second list.

Done when a reader can skip the bullet lists and still know what to find.

### 3. Name the asterism that is already on the charts

Night 1’s first disc and look-ahead already show Vega, Altair, and Deneb. They are never called the Summer Triangle. No new stars.

When those three are up together, say so in the notice line and on the look-ahead. Same pattern later for whatever triple a later stop actually has — only if all three are in `sky.json` for that sample. Dawn on Night 1 already has Orion’s shoulders on the disc; that is a second memory if the triangle has set.

Done when the first stop is rememberable as a triangle over a ridge, not three mag numbers.

### 4. Read the night as a sequence

Night 1 is four independent ledes. The moon is up at the first stop and behind the ridge at the rest. Overhead names shift from Aquila / Cygnus / Lyra to Pegasus to Orion. Nothing says that.

After the stop list, one short block from the ordered samples: the moon’s hinge, then what rose. Sentence form. The altitude panels already show Vega dropping and Orion climbing — do not paste those charts here; one sentence is enough.

Done when Night 1 reads as a night that turns, not four km cards.

### 5. Constellation cards for what this stop actually shows

IAU plates exist. There is still no hook, and no “how to find it from here”. The Night 1 IAU page is 27 names.

Add a small static table in-repo keyed by constellation names this race already emits — Cygnus, Lyra, Aquila, Pegasus, Andromeda, Orion, and the others that appear in the current night lists. Two sentences each: a hook, and how to catch it using a star we already plot (Deneb for Cygnus, Vega for Lyra, Betelgeuse for Orion). Render a card only when that constellation is overhead on that sample, under the disc, linking to the IAU plate.

Write the table from the live page’s overhead lists, not from the IAU 88. Skip Crux if it never rises here.

Done when a stop is followed by at most two or three cards, not a dump of fifteen names.

### 6. Night 1 vs Night 2 as one sky, two ridges

The two nights already link. The same stars are in `sky.json` for both. Nothing compares them.

After Night 2’s look-ahead, one short block: the named star or asterism from Night 1, where it sits on Night 2’s look-ahead (left / ahead / right, above or behind the DSM). Sentence form, not a new plot, unless a two-panel of the two look-aheads is clearer.

Done when the page says, in effect: same swan, different mountain.

## After that

**Early on the cutoff.** The course page already prints optimistic / realistic / conservative kilometre spans. Faster running is a second distance at the same dusk clock, then the same look-ahead. One extra sample set, not a live slider. Show it only if the look-ahead actually changes (different ridge or different ahead star).

**Nearest aid.** `checkpoints.csv` already has names and kilometres. One line on the stop page: the next checkpoint, how far. So someone can actually stand still. Derive it; do not type place names into `report.py`.

**A card worth keeping.** A square PNG from the look-ahead plus the notice line plus the stop name — `plots.py` already writes PNGs; the page already has `download`. No new data. For after the race, not during it.

**What you saw.** Pages will not store it. A GitHub issue template (“km, night, what was overhead”) or a blank line on the card PNG. That is the whole feature.

## Not this

A WebGL / canvas planetarium. Streaming stars. Constellation stick figures from a survey catalogue.

Weather APIs. Moon illumination on the sample is the wash signal we have.

A second race, a pace UI, or a backend, until a stop has a name and a sentence someone might remember.
