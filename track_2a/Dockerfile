FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 CACHE_DIR=/work/.cache BOOKLET_ROOT=/data
WORKDIR /app
COPY pyproject.toml ./
COPY src/booklint ./src/booklint
RUN pip install .
WORKDIR /work
ENTRYPOINT ["booklint"]
CMD ["--help"]
