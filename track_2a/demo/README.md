# GeaNaVid web demo

A small web UI and JSON API in front of the default `booklint` pipeline. The API returns the OST output
format (slide 25 of the OST track session): `id`, `label`, `label_name`, `evidence` (`[{page, text}]`, empty
for neutral) and `metrics` (`input_tokens`, `output_tokens`, `inference_time_ms`, measured on this request).

- **Beginner task:** claim + reference passage (classify directly).
- **Advanced task:** claim + one of the official booklets of the OST v1.0 dataset (by date, `de`/`fr`/`it`)
  + optional vote title (retrieve, then classify). Arbitrary URLs or paths are not accepted.
- **Examples:** six real OST v1.0 cases from the development split (Advanced task: E, C and N, de/fr/it,
  four cross-lingual; ids in `OST_EXAMPLE_IDS` in `server.py`), and the 24 synthetic edge cases from
  `data/edge_cases.jsonl` (LLM-written, not reviewed, not part of the OST benchmark, never evaluated).
- **Same answer as the CLI:** the page shows the `booklint predict` call that runs the same pipeline
  (default options, model from `LLM_NAME`). Checked on 2026-10-04 for v1-0161, v1-1484 and v1-0696:
  same labels and evidence as the CLI with `--no-cache`.

## Run locally

```bash
cd track_2a
export LLM_BASE_URL=... LLM_API_KEY=... LLM_NAME=apertus-v1.5-8b   # or track_2a/.env
export BASIC_AUTH_USER=... BASIC_AUTH_PASSWORD=...                 # required unless --no-auth
python demo/server.py --port 8080            # or: python demo/server.py --no-auth (local only)
```

Open `http://localhost:8080`. The browser asks for the Basic Auth credentials once; the page itself holds no
credentials and the LLM key never leaves the server.

| Variable                                  | Default | Meaning                                                    |
| ----------------------------------------- | ------- | ---------------------------------------------------------- |
| `BASIC_AUTH_USER`, `BASIC_AUTH_PASSWORD`  | –       | required, no default                                       |
| `RATE_LIMIT_MAX`, `RATE_LIMIT_WINDOW`     | 20, 60  | requests per client IP and window (s), then HTTP 429       |
| `TRUST_PROXY`                             | off     | `1`: take the client IP from the last `X-Forwarded-For` hop |
| `DEMO_LLM_CACHE`                          | off     | `1`: reuse cached LLM answers (then the time is not inference time) |

## API

- `GET /api/health` – public.
- `GET /api/presets`, `GET /api/info` – Basic Auth.
- `POST /api/predict` – Basic Auth and rate limit. Body:
  `{"id": "demo-01", "mode": "beginner", "claim": "...", "reference": "..."}` or
  `{"mode": "advanced", "claim": "...", "booklet": "2024-11-24", "booklet_lang": "de", "vote": "..."}`.
  Errors: 400 invalid input, 401, 413 body over 16 KB, 429 rate limit, 502 inference failed,
  503 LLM backend not configured. There is no fallback answer: a failed call is an error, not a label.

## Deployment

Online at `https://geanavid.apertool.ch/demo/` behind Basic Auth (preview, `noindex`). `website/docker-compose.yml`
runs two services: `web` (nginx, static site and `website/demo/`) and `demo` (`server.py`, built from
`track_2a/` with `demo/Dockerfile`). nginx forwards `/api/` to `demo:8080`; Basic Auth covers the whole site
including `/api/`, and `server.py` checks the same credentials again. The CSP allows inline styles only under
`/demo/`. `TRUST_PROXY=1` is set in Compose because nginx always stands in front of the demo service; nginx
passes on the `X-Forwarded-For` header from the reverse proxy unchanged, so the rate limit counts per client.

Coolify app: base directory `/website`, Compose file `/docker-compose.yml`, environment `BASIC_AUTH_USER`,
`BASIC_AUTH_PASSWORD`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_NAME`. Compose stops with an error if one of the
required values is missing. The LLM key stays in the `demo` container.

Local test: copy `website/.env.example` to `website/.env`, fill it in, publish a port for `web` in an override
file and run `docker compose up --build` in `website/`.
