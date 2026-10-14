FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 CACHE_DIR=/app/.cache
WORKDIR /app
COPY requirements.lock pyproject.toml ./
RUN pip install -r requirements.lock
COPY src/booklint ./src/booklint
RUN pip install --no-deps .
COPY demo/server.py ./demo/server.py
COPY data/edge_cases.jsonl ./data/edge_cases.jsonl
COPY data/v1/v1.0.jsonl data/v1/vote-titles.json ./data/v1/
RUN useradd --system --no-create-home demo && mkdir -p /app/.cache && chown demo /app/.cache
USER demo
EXPOSE 8080
CMD ["python", "demo/server.py", "--host", "0.0.0.0", "--port", "8080"]
