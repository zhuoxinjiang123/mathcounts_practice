FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MATHCOUNTS_HOST=0.0.0.0
ENV PORT=8000
ENV MATHCOUNTS_DB_PATH=/app/docker-data/app.sqlite3
ENV MATHCOUNTS_CATALOG_PATH=/app/data/catalog.json
ENV MATHCOUNTS_ANSWER_KEYS_PATH=/app/data/answer_keys.csv

COPY . /app

RUN mkdir -p /app/docker-data

EXPOSE 8000

CMD ["python3", "-m", "mathcounts_platform.bootstrap"]
