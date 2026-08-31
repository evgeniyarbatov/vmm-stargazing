# uv: https://docs.astral.sh/uv — deps via `make install`, run with `uv run`.
DATA_ROOT ?= $(HOME)/Documents/data
DATA_DIR  ?= $(DATA_ROOT)/vmm-stargazing
SITE_DIR  ?= $(CURDIR)/docs

CONFIG ?= config.yaml
GPX ?=
DENSIFY_M ?= 10
BUFFER_KM ?= 15
SAMPLE_M ?=

SAMPLE_FLAG = $(if $(strip $(SAMPLE_M)),--sample-m $(SAMPLE_M),)

BBOX_JSON = $(DATA_DIR)/bbox.json
CLEANED_GPX = $(DATA_DIR)/input.gpx
DEM_TIF = $(DATA_DIR)/dem/glo30.tif
NIGHTS = $(DATA_DIR)/nights.json
SAMPLES = $(DATA_DIR)/samples.json
SKY = $(DATA_DIR)/sky.json

.PHONY: install lock test lint help \
	gpx dem timeline sky plots site run \
	clean clean-dem

install:
	@uv sync --group dev

lock:
	@uv lock

test: install
	@uv run python -m unittest discover -s tests -p "test_*.py" -v

lint: install
	@uv run ruff check scripts tests

gpx: install
	@mkdir -p "$(DATA_DIR)/gpx"
	@if [ -n "$(strip $(GPX))" ]; then \
		uv run python scripts/gpx.py --config "$(CONFIG)" --data-dir "$(DATA_DIR)" \
			--densify-m $(DENSIFY_M) --gpx "$(GPX)"; \
	else \
		uv run python scripts/gpx.py --config "$(CONFIG)" --data-dir "$(DATA_DIR)" \
			--densify-m $(DENSIFY_M); \
	fi

dem: install
	@test -f "$(BBOX_JSON)" || (echo "Error: missing $(BBOX_JSON). Run: make gpx GPX=…" >&2; exit 1)
	@mkdir -p "$(DATA_DIR)/dem"
	@uv run python scripts/dem.py "$(BBOX_JSON)" \
		--out "$(DEM_TIF)" \
		--buffer-km $(BUFFER_KM)

timeline: install
	@test -f "$(CLEANED_GPX)" || (echo "Error: missing $(CLEANED_GPX). Run: make gpx GPX=…" >&2; exit 1)
	@uv run python scripts/timeline.py --config "$(CONFIG)" --data-dir "$(DATA_DIR)" \
		$(SAMPLE_FLAG)

sky: install
	@test -f "$(SAMPLES)" || (echo "Error: missing $(SAMPLES). Run: make timeline" >&2; exit 1)
	@uv run python scripts/sky.py --config "$(CONFIG)" --data-dir "$(DATA_DIR)"

plots: install
	@test -f "$(SKY)" || (echo "Error: missing $(SKY). Run: make sky" >&2; exit 1)
	@mkdir -p "$(SITE_DIR)/plots"
	@uv run python scripts/plots.py --config "$(CONFIG)" --data-dir "$(DATA_DIR)" \
		--site-dir "$(SITE_DIR)"

site: install
	@test -f "$(SKY)" || (echo "Error: missing $(SKY). Run: make sky" >&2; exit 1)
	@mkdir -p "$(SITE_DIR)"
	@uv run python scripts/report.py --config "$(CONFIG)" --data-dir "$(DATA_DIR)" \
		--site-dir "$(SITE_DIR)"

run: gpx dem timeline sky plots site
	@echo "Done: $(SITE_DIR)"

clean:
	@rm -f "$(NIGHTS)" "$(SAMPLES)" "$(SKY)"
	@echo "Cleaned nights/samples/sky under $(DATA_DIR)"

clean-dem:
	@rm -f "$(DEM_TIF)"
	@echo "Removed $(DEM_TIF)"

help:
	@echo "install     - uv sync deps"
	@echo "lock        - refresh uv.lock"
	@echo "test        - run unit tests"
	@echo "lint        - ruff check scripts tests"
	@echo "gpx         - densify in-repo GPX + bbox → \$$(DATA_DIR)/ (GPX= overrides)"
	@echo "dem         - cache Copernicus GLO-30 for bbox"
	@echo "timeline    - astronomical night windows + along-track samples"
	@echo "sky         - planets, moon, stars, terrain horizon"
	@echo "plots       - course map, sky discs, altitude / spots → docs/plots/"
	@echo "site        - GitHub Pages HTML + data.json under docs/"
	@echo "run         - gpx → dem → timeline → sky → plots → site"
	@echo "clean       - remove nights/samples/sky (keep DEM + ephemeris + docs/)"
	@echo "clean-dem   - remove cached DEM"
	@echo ""
	@echo "Data: \$$(DATA_DIR) (default ~/Documents/data/vmm-stargazing)."
	@echo "Site: \$$(SITE_DIR) (default ./docs)."
	@echo "Knobs: DENSIFY_M BUFFER_KM SAMPLE_M"
	@echo "Example: make run"
