#!/usr/bin/env bash
# RUN-134: Generate TypeScript types + Zod schemas from FastAPI OpenAPI spec
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OPENAPI_JSON="$REPO_ROOT/openapi.json"
GENERATED_DIR="$REPO_ROOT/packages/shared/src"

# Step 1: Extract OpenAPI spec from FastAPI app
echo "Extracting OpenAPI spec..."
uv run --package runsight python -c "
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

# openapi-typescript treats defaulted component properties as required by
# default. RunCreate is a write contract, so defaulted request fields must stay
# optional for callers while the server and Zod schemas still apply defaults.
uv run python - "$GENERATED_DIR/api.ts" << 'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text()
start_marker = "        /** RunCreate */\n        RunCreate: {"
end_marker = "        /** RunEvalResponse */"
start = source.index(start_marker)
end = source.index(end_marker, start)
block = source[start:end]
replacements = {
    "            inputs: {": "            inputs?: {",
    "            source: string | null;": "            source?: string | null;",
    "            branch: string;": "            branch?: string;",
}
for old, new in replacements.items():
    if old not in block:
        raise SystemExit(f"RunCreate generated contract missing expected field: {old}")
    block = block.replace(old, new, 1)
path.write_text(source[:start] + block + source[end:])
PY

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
