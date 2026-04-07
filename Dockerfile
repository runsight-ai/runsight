# ──────────────────────────────────────────────
# Stage 1: Build frontend
# ──────────────────────────────────────────────
FROM node:20-slim AS frontend-build

RUN corepack enable && corepack prepare pnpm@9 --activate

WORKDIR /app

# Copy workspace manifests first (layer caching)
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/gui/package.json apps/gui/
COPY packages/shared/package.json packages/shared/
COPY packages/ui/package.json packages/ui/

RUN pnpm install --frozen-lockfile

# Copy source for GUI and its workspace dependencies
COPY apps/gui/ apps/gui/
COPY packages/shared/ packages/shared/
COPY packages/ui/ packages/ui/

RUN pnpm -C apps/gui run build:bundle

# ──────────────────────────────────────────────
# Stage 2: Python runtime
# ──────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# System deps: git (GitOps features), curl (healthcheck)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy Python workspace manifests
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/
COPY packages/core/pyproject.toml packages/core/

# Copy Python source
COPY apps/api/src/ apps/api/src/
COPY packages/core/src/ packages/core/src/

# Install Python dependencies (production only)
RUN uv sync --frozen --all-packages --no-dev

# Copy built frontend from stage 1
COPY --from=frontend-build /app/apps/gui/dist /app/static

# Copy entrypoint
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

ENV RUNSIGHT_BASE_PATH=/workspace \
    RUNSIGHT_STATIC_DIR=/app/static \
    RUNSIGHT_LOG_FORMAT=text

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "runsight_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
