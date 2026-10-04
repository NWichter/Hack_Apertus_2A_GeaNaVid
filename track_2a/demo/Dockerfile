FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 CACHE_DIR=/app/.cache
WORKDIR /app
COPY pyproject.toml ./
COPY src/booklint ./src/booklint
RUN pip install .
COPY demo/server.py ./demo/server.py
COPY data/edge_cases.jsonl ./data/edge_cases.jsonl
COPY data/v1/v1.0.jsonl ./data/v1/v1.0.jsonl
RUN useradd --system --no-create-home demo && mkdir -p /app/.cache && chown demo /app/.cache
USER demo
EXPOSE 8080
CMD ["python", "demo/server.py", "--host", "0.0.0.0", "--port", "8080"]
