FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 CACHE_DIR=/tmp/booklint BOOKLET_ROOT=/data
# Model used when OST runs the image (OST sets only BASE_URL and API_KEY). Default: apertus-v1.5-8b.
# Recommended for the evaluation: [[NIKLAS: Modellwahl]]. For 70B uncomment the next line
# (test v1.1: 8B 0.959 / 2,159 input tokens / p95 545 ms; 70B 0.965 / 1,461 / 2,197 ms).
# ENV LLM_NAME=apertus-v1.5-70b
WORKDIR /app
COPY pyproject.toml ./
COPY src/booklint ./src/booklint
RUN pip install .
WORKDIR /work
ENTRYPOINT ["booklint"]
CMD ["--help"]
