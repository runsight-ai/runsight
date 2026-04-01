#!/usr/bin/env bash
# RUN-134: Generate TypeScript types + Zod schemas from FastAPI OpenAPI spec
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OPENAPI_JSON="$REPO_ROOT/openapi.json"
GENERATED_DIR="$REPO_ROOT/packages/shared/src"

# Step 1: Extract OpenAPI spec from FastAPI app
echo "Extracting OpenAPI spec..."
uv run --package runsight-api python -c "
from runsight_api.main import app
import json
spec = app.openapi()
with open('$OPENAPI_JSON', 'w') as f:
    json.dump(spec, f, indent=2)
    f.write('\n')
"

# Step 2: Generate TypeScript types using openapi-typescript
echo "Generating TypeScript types..."
mkdir -p "$GENERATED_DIR"
cd "$REPO_ROOT/packages/shared"
npx openapi-typescript "$OPENAPI_JSON" -o "$GENERATED_DIR/api.ts"

# Keep a runtime export alongside the type-only namespace so the generated
# module can be imported in tests without being fully erased at runtime.
cat >> "$GENERATED_DIR/api.ts" << 'API_RUNTIME_SHIM'

export const components = {};
API_RUNTIME_SHIM

# Step 3: Generate Zod schemas
echo "Generating Zod schemas..."
uv run python "$REPO_ROOT/tools/generate-zod-schemas.py" \
  "$OPENAPI_JSON" \
  "$GENERATED_DIR/zod.ts"

# Step 4: Generate barrel export
echo "Generating barrel export..."
cat > "$GENERATED_DIR/index.ts" << 'BARREL'
export * from "./api";
export * from "./zod";
BARREL

echo "Done! Generated types in $GENERATED_DIR"
