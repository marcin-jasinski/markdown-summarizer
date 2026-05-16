# Stage 1: build Angular SPA
FROM node:20-alpine AS builder
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -r -m -s /bin/false appuser
WORKDIR /app
COPY pyproject.toml ./
COPY mindforge/ ./mindforge/
COPY migrations/ ./migrations/
RUN pip install --no-cache-dir -e .
COPY --from=builder /build/frontend/dist/ ./frontend/dist/
RUN chown -R appuser:appuser /app
LABEL org.opencontainers.image.source="https://github.com/mindforge/mindforge"
LABEL org.opencontainers.image.version="2.0.0"
USER appuser
EXPOSE 8080
CMD ["mindforge-api"]
