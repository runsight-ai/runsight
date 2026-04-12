#!/bin/sh
set -e

# Activate the virtual environment
export PATH="/app/.venv/bin:$PATH"

# Default workspace to /workspace if not set
: "${RUNSIGHT_BASE_PATH:=/workspace}"
export RUNSIGHT_BASE_PATH

# Fail-fast: workspace must be pre-created and mounted by the host
if [ ! -d "$RUNSIGHT_BASE_PATH" ]; then
    echo "[runsight] ERROR: Workspace '$RUNSIGHT_BASE_PATH' does not exist." >&2
    echo "[runsight] Mount a volume: docker run -v \$(pwd):/workspace ..." >&2
    exit 1
fi

# Warn if workspace is empty
if [ -z "$(ls -A "$RUNSIGHT_BASE_PATH" 2>/dev/null)" ]; then
    echo "[runsight] Empty workspace at $RUNSIGHT_BASE_PATH — Runsight will scaffold a new project."
fi

exec "$@"
