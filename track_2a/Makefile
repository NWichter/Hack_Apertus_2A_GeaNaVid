.PHONY: run build test ost

# Everything runs in Docker. Model access: LLM_NAME, LLM_BASE_URL, LLM_API_KEY in the environment or in
# track_2a/.env (see .env.example).
INPUT ?= data/v1/test_v11.jsonl
MODES ?= retrieval
MODELS ?=
LIMIT ?= 0
ROWS ?= 20
PY_IMAGE ?= python:3.12-slim

# Benchmark: the default pipeline on the OST v1.1 test split (493 claims); table in runs/make-run/summary.md.
# Quick check: make run LIMIT=30. Whole-booklet baseline for comparison: make run MODES=retrieval,baseline
run: build
	docker compose run --rm booklint bench --input $(INPUT) --modes $(MODES) --models "$(MODELS)" --limit $(LIMIT) --workers 4 --out-dir runs/make-run

build:
	docker compose build

# Unit tests (no model calls) in a clean Python container.
test:
	docker run --rm -v "$(CURDIR):/src:ro" $(PY_IMAGE) sh -c "cp -r /src /tmp/t && cd /tmp/t && pip install -q --root-user-action=ignore '.[test]' && python -m pytest -q -p no:cacheprovider"

# OST's contract on a sample of the test split: ROWS rows as task A and task B, the image run exactly as in OST's
# Solution API Guide (read-only /data, --input/--output), then scored like OST's evaluate.py. Results in runs/ost-sample/.
ost:
	docker build -q -t geanavid .
	docker run --rm -v "$(CURDIR):/src" -w /src $(PY_IMAGE) sh -c "pip install -q --root-user-action=ignore . && python experiments/v1/ost_cases.py --split test_v11 --rows $(ROWS) --out runs/ost-sample/data"
	docker run --rm --env-file .env -v "$(CURDIR)/runs/ost-sample/data:/data:ro" -v "$(CURDIR)/runs/ost-sample/output:/output" geanavid --input /data/cases.jsonl --output /output/predictions.jsonl
	docker run --rm -v "$(CURDIR):/src:ro" -w /src $(PY_IMAGE) sh -c "pip install -q --root-user-action=ignore rapidfuzz && python experiments/v1/ost_score.py --predictions runs/ost-sample/output/predictions.jsonl --expected runs/ost-sample/data/expected-labels.jsonl"
