.PHONY: run build test smoke

INPUT ?= data/v1/test_v11.jsonl
MODES ?= retrieval
MODELS ?=
LIMIT ?= 0

# Benchmark in Docker with the default pipeline against LLM_BASE_URL / LLM_API_KEY / LLM_NAME
# (environment or track_2a/.env). Results: runs/make-run/summary.md and one JSONL per model and mode.
# Quick check: make run LIMIT=30. Whole-booklet baseline for comparison: make run MODES=retrieval,baseline
run: build
	docker compose run --rm booklint bench --input $(INPUT) --modes $(MODES) --models "$(MODELS)" --limit $(LIMIT) --workers 4 --out-dir runs/make-run

build:
	docker compose build

# Offline: parse one booklet, no LLM calls.
smoke: build
	docker compose run --rm booklint ingest --booklet https://www.bk.admin.ch/dam/de/sd-web/WeUrKyC0FyPc/2026-06-14_erlaeuterungen_des_bundesrates.pdf

test:
	python -m pytest -q
