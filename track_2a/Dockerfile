# python:3.12-slim (3.12.15), pinned by digest on 15 October 2026
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 CACHE_DIR=/tmp/booklint BOOKLET_ROOT=/data
# Model used when OST runs the image (OST sets only BASE_URL and API_KEY): Apertus v1.5 70B, named as in OST's
# Solution API Guide; if the endpoint calls it differently, the CLI takes the 70B model from /models (WARNING on stderr).
# Why 70B: macro-F1 0.965 on the OST v1.1 test split (8B 0.959), fewer input tokens (1,461 vs 2,159) and more robust on
# older booklets (synthetic stress set); 8B is faster (cold p95 545 vs 2,197 ms). For 8B: -e LLM_NAME=apertus-v1.5-8b
ENV LLM_NAME=swiss-ai/Apertus-v1.5-70B
WORKDIR /app
COPY requirements.lock pyproject.toml ./
RUN pip install -r requirements.lock
COPY src/booklint ./src/booklint
RUN pip install --no-deps .
WORKDIR /work
ENTRYPOINT ["booklint"]
CMD ["--help"]
