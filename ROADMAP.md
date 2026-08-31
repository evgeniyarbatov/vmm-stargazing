# Roadmap

Two jobs: make someone curious enough to look up, and leave them with a constellation tied to a ridge. The end of that is thinking bigger. VMM 2026 is the place that happens — not a generic ultra tool.

The site is a precomputed field notebook (`docs/`, PNGs + HTML). It is not a planetarium.

## Already in the notebook

Checkpoint-cutoff pace along the GPX (`checkpoints.csv` → `timeline.py`). True night windows. Along-track samples only in those windows.

At each sample: planets Mercury–Saturn, Moon phase, ~60 named stars with a constellation label, Milky Way centre, GLO-30 DSM horizon (`sky.json`).

On the page: course and profile; a scored “best stop” per night; a DSM look-ahead from that stop, facing the GPX; sky discs at dusk / midnight / dawn; separate planet and star altitude charts; lists of planets, constellations, bright stars; chart and `data.json` downloads.

Constellation “presence” is: at least one catalogued star from that constellation is up. Discs and look-aheads draw a nav-star subset, not stick figures.

## Hard limits

GLO-30 is a ~30 m DSM with 15 km rays. Ridges and valleys, not the tread. Horizon masking is topographic context.

Planet alt/az barely move across this bbox. Where you stand, and the ridge in front of you, do.

Samples are discrete (about 2 km, capped per night). There is no interpolation of the sky between them.

GitHub Pages cannot store “what I saw”. No form, no database.

`make test` stays offline. No live Copernicus, no live planetarium, no Hipparcos / constellation-line catalogue.

## Do next

Work in this order. Each item is one change to the existing pipeline, then `make plots site`.

### 1. Name the two stops

The look-aheads are already the best-scored sample per night (`km 42` and `km 122` on the current page). The map still labels `km · score`. The night heading is still a clock time.

Pick a name from data already on that sample: the star marked ahead, or the overhead constellation if nothing is in the heading cone. Use it on the spots map, the look-ahead title, and the night `<h2>` subtitle.

Done when Night 1’s stop is something like “Deneb, km 42” and Night 2 is named from its own look-ahead, not `0.71`.

### 2. One notice line under each picture

`report.py` already writes a moon sentence, a Milky Way sentence, and a dumped constellation list. The night lede concatenates those. Each disc has no “if you stop, look at this”.

Add one function that returns a single sentence from the sample + `sky.json` row: the ahead star against the DSM, or Moon wash, or Milky Way centre if it is up. Put it under the look-ahead and under each dusk / midnight / dawn disc. Do not add a second list.

Done when a reader can skip the bullet lists and still know what to find.

### 3. Name the asterism that is already on the charts

Night 1’s disc and look-ahead already show Vega, Altair, and Deneb. They are never called the Summer Triangle. No new stars.

When those three are up together, say so in the notice line and on the look-ahead. Same pattern later for whatever triple the second night actually has — only if all three are in `sky.json` for that sample.

Done when Night 1’s stop is rememberable as a triangle over a ridge, not three mag numbers.

### 4. Constellation cards for what this race actually shows

There is no myth text and no “how to find it from here”. Drawing IAU lines would be a new catalogue (out of scope).

Add a small static table in-repo (YAML or similar) keyed by the constellation names already emitted for VMM — Cygnus, Lyra, Aquila, Pegasus, Andromeda, and the others that appear in the current night lists. Two sentences each: a hook, and how to catch it using a star we already plot (Deneb for Cygnus, Vega for Lyra). Render a card only when that constellation is overhead or up on that sample.

Write the table from the live page’s constellation lists, not from the IAU 88. Skip Crux if it never rises here.

Done when a disc is followed by at most two or three cards, not a dump of fifteen names.

### 5. Night 1 vs Night 2 as one sky, two ridges

The two nights are separate chapters. The same stars are in `sky.json` for both. Nothing compares them.

After Night 2’s look-ahead, one short block: the named star or asterism from Night 1, where it sits on Night 2’s look-ahead (left / ahead / right, above or behind the DSM). Sentence form, not a new plot, unless a two-panel of the two look-aheads is clearer.

Done when the page says, in effect: same swan, different mountain.

## After that

**Early on the cutoff.** `timeline.py` already maps clock time to distance along the checkpoint knots. Faster running is a second distance at the same dusk / midnight / dawn clocks, then the same `sky.py` / look-ahead. One extra sample set, not a live slider. Show it only if the look-ahead actually changes (different ridge or different ahead star).

**A card worth keeping.** A square PNG from the look-ahead plus the notice line plus the stop name — `plots.py` already writes PNGs; the page already has `download`. No new data. For after the race, not during it.

**What you saw.** Pages will not store it. A GitHub issue template (“km, night, what was overhead”) or a blank line on the card PNG. That is the whole feature.

## Not this

A WebGL / canvas planetarium. Streaming stars. Constellation stick figures from a survey catalogue.

Weather APIs. Moon illumination on the sample is the wash signal we have.

A second race, a pace UI, or a backend, until this page has a stop with a name and a sentence someone might remember.
