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
}
for old, new in replacements.items():
    if old not in block:
        raise SystemExit(f"RunCreate generated contract missing expected field: {old}")
    block = block.replace(old, new, 1)
inputs_record = """            inputs?: {
                [key: string]: unknown;
            };"""
if inputs_record not in block:
    raise SystemExit("RunCreate generated contract missing expected inputs record shape")
block = block.replace(inputs_record, "            inputs?: Record<string, unknown>;", 1)
path.write_text(source[:start] + block + source[end:])
PY

# Keep generated response map fields compact so component field extraction in
# contract tests can see fields that follow them.
uv run python - "$GENERATED_DIR/api.ts" << 'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text()
start_marker = "        /** RunResponse */\n        RunResponse: {"
end_marker = "        /** SettingsFallbackListResponse */"
start = source.index(start_marker)
end = source.index(end_marker, start)
block = source[start:end]
replacements = {
    """            source_metadata?: {
                [key: string]: unknown;
            };""": "            source_metadata?: Record<string, unknown>;",
    """            workflow_inputs?: {
                [key: string]: unknown;
            } | null;""": "            workflow_inputs?: Record<string, unknown> | null;",
    """            workflow_input_schema?: {
                [key: string]: unknown;
            } | null;""": "            workflow_input_schema?: Record<string, unknown> | null;",
}
for old, new in replacements.items():
    if old not in block:
        raise SystemExit(f"RunResponse generated contract missing expected map field: {old}")
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
