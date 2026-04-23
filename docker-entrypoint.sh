#!/bin/sh
set -e

# Activate the virtual environment
export PATH="/app/.venv/bin:$PATH"

# API pytest config injects RUNSIGHT_BASE_PATH=tempdir for in-process tests.
# That inherited default should not override the container's mounted workspace root.
if [ -n "${PYTEST_CURRENT_TEST:-}" ] && [ -n "${RUNSIGHT_BASE_PATH:-}" ]; then
    normalized_tmpdir=${TMPDIR%/}
    if [ -n "$normalized_tmpdir" ] && [ "$RUNSIGHT_BASE_PATH" = "$normalized_tmpdir" ]; then
        unset RUNSIGHT_BASE_PATH
    fi
fi

# Default to the mounted workspace root when no explicit override is provided.
: "${RUNSIGHT_BASE_PATH:=/workspace}"
export RUNSIGHT_BASE_PATH

# Fail fast when workspace is absent — init-permissions must own it before
# this container starts (AC5). A non-root container cannot create
# root-owned directories at runtime.
if [ ! -d "$RUNSIGHT_BASE_PATH" ]; then
    echo "[runsight] ERROR: workspace '$RUNSIGHT_BASE_PATH' does not exist." >&2
    echo "[runsight] Mount a volume before starting the container." >&2
    exit 1
fi

# Inform when workspace is empty — Runsight will scaffold custom/ and .runsight/
# under the workspace root.
if [ -z "$(ls -A "$RUNSIGHT_BASE_PATH" 2>/dev/null)" ]; then
    echo "[runsight] Empty workspace at $RUNSIGHT_BASE_PATH — Runsight will scaffold a new workspace."
fi

exec "$@"
