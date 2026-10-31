# Build and scan this image in the deployment region before enabling WAL archiving.
FROM postgres:15-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends pgbackrest ca-certificates \
    && rm -rf /var/lib/apt/lists/*
