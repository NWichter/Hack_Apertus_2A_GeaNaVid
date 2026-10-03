# GeaNaVid web demo

A small web UI and JSON API in front of the default `booklint` pipeline. The API returns the OST output
format (slide 25 of the OST track session): `id`, `label`, `label_name`, `evidence` (`[{page, text}]`, empty
for neutral) and `metrics` (`input_tokens`, `output_tokens`, `inference_time_ms`, measured on this request).

- **Beginner task:** claim + reference passage (classify directly).
- **Advanced task:** claim + one of the official booklets of the OST v1.0 dataset (by date, `de`/`fr`/`it`)
  + optional vote title (retrieve, then classify). Arbitrary URLs or paths are not accepted.
- **Presets:** the 24 synthetic edge cases from `data/edge_cases.jsonl` (LLM-written, not reviewed, not part
  of the OST benchmark).

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

## Deployment status

Not deployed. `website/demo/` holds a copy of the static files (`index.html`, `demo.js`, `demo.css`), but the
website container is plain nginx: it has no `/api/*` route, so on the website the form cannot get an answer
(the page shows "The demo API is not reachable"). The website CSP (`style-src 'self'`) also blocks the
inline `style` attributes the result view uses. Running the demo publicly needs `server.py` as its own
service (e.g. a second Compose service built from `track_2a/`) and either an nginx `location /api/`
proxy to it or a separate domain, plus `TRUST_PROXY=1` behind the proxy.
