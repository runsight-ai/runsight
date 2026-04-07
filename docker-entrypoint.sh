#!/bin/sh
set -e

# Activate the virtual environment
export PATH="/app/.venv/bin:$PATH"

# Default workspace to /workspace if not set
: "${RUNSIGHT_BASE_PATH:=/workspace}"
export RUNSIGHT_BASE_PATH

# Ensure workspace directory exists
if [ ! -d "$RUNSIGHT_BASE_PATH" ]; then
    mkdir -p "$RUNSIGHT_BASE_PATH"
    echo "[runsight] Created workspace at $RUNSIGHT_BASE_PATH"
    echo "[runsight] WARNING: No volume mounted — data will not persist when the container stops."
    echo "[runsight] Mount a volume: docker run -v \$(pwd):/workspace ..."
fi

# Warn if workspace is empty
if [ -z "$(ls -A "$RUNSIGHT_BASE_PATH" 2>/dev/null)" ]; then
    echo "[runsight] Empty workspace at $RUNSIGHT_BASE_PATH — Runsight will scaffold a new project."
fi

exec "$@"
