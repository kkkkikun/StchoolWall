# syntax=docker/dockerfile:1
FROM python:3.10-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
ARG CONSTRAINTS_SHA256=unconstrained
# CI injects the complete constraints from the passing backend test environment.
RUN --mount=type=secret,id=constraints,target=/tmp/tested-constraints.txt \
    if [ -f /tmp/tested-constraints.txt ]; then \
      test "$(sha256sum /tmp/tested-constraints.txt | cut -d ' ' -f1)" = "$CONSTRAINTS_SHA256" && \
      pip install --no-cache-dir -r requirements.txt -c /tmp/tested-constraints.txt; \
    else pip install --no-cache-dir -r requirements.txt; fi
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
RUN groupadd --gid 10001 schoolwall && useradd --uid 10001 --gid schoolwall --no-create-home schoolwall \
    && mkdir -p /data/static /data/private-media /data/private-verifications && chown -R schoolwall:schoolwall /data /app
ENV STATIC_BASE_DIR=/data/static
VOLUME ["/data/static", "/data/private-media", "/data/private-verifications"]
USER schoolwall
EXPOSE 8000
# Migrations are a single release job, never an API/worker startup side effect.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--proxy-headers"]
