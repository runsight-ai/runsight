# ──────────────────────────────────────────────
# Stage 1: Build frontend
# ──────────────────────────────────────────────
FROM node:20-slim AS frontend-build

RUN corepack enable && corepack prepare pnpm@10 --activate

WORKDIR /app

# Copy all workspace manifests (layer caching)
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/gui/package.json apps/gui/
COPY packages/shared/package.json packages/shared/
COPY packages/ui/package.json packages/ui/

RUN pnpm install --frozen-lockfile

# Copy source for GUI and its workspace dependencies
# Use specific subdirs to avoid overwriting node_modules
COPY apps/gui/src/ apps/gui/src/
COPY apps/gui/index.html apps/gui/tsconfig*.json apps/gui/vite.config.ts apps/gui/
COPY packages/shared/src/ packages/shared/src/
COPY packages/shared/tsconfig*.json packages/shared/
COPY packages/ui/src/ packages/ui/src/
COPY packages/ui/*.ts packages/ui/*.tsx packages/ui/

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

# Create non-root user and pre-create the mounted workspace.
RUN groupadd --gid 1000 runsight && \
    useradd --uid 1000 --gid runsight --shell /bin/sh --create-home runsight && \
    mkdir -p /workspace && \
    chown runsight:runsight /workspace

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

# Configure git safe directory (must run AFTER USER runsight so it writes to /home/runsight/.gitconfig)
USER runsight
RUN git config --global --add safe.directory /workspace

ENV RUNSIGHT_BASE_PATH=/workspace \
    RUNSIGHT_STATIC_DIR=/app/static \
    RUNSIGHT_LOG_FORMAT=text

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["runsight"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
