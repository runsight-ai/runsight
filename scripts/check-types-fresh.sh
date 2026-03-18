#!/usr/bin/env bash
# RUN-134: CI freshness check — regenerates types and diffs against committed files
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Regenerate types
"$REPO_ROOT/scripts/generate-types.sh"

# Check for drift
if ! git diff --exit-code -- openapi.json apps/gui/src/types/generated/; then
  echo "ERROR: Generated types are stale. Run 'scripts/generate-types.sh' and commit the result."
  exit 1
fi

echo "Generated types are fresh."
