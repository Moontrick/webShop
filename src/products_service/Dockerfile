FROM python:3.9-slim

ARG SERVICE_DIR=products_service

RUN apt-get update && apt-get install -y --no-install-recommends build-essential  && rm -rf /var/lib/apt/lists/*


ENV PYTHONUNBUFFERED=1  PYTHONDONTWRITEBYTECODE=1  PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY $SERVICE_DIR/poetry.lock $SERVICE_DIR/pyproject.toml ./

RUN pip install --no-cache-dir poetry &&  poetry lock &&  poetry config virtualenvs.create false &&  poetry install --no-root --no-interaction --no-ansi