import urllib.request
import json
import sys

MODELS = {
    "default": "claude-haiku-4-5-20251001",
    "coder": "claude-haiku-4-5-20251001",
    "pm": "claude-sonnet-4-6",
    "architect": "claude-sonnet-4-6",
    "tech_lead": "claude-sonnet-4-6",
    "sprint_planner": "claude-sonnet-4-6",
    "code_reviewer": "claude-sonnet-4-6",
    "qa": "claude-sonnet-4-6",
    "verifier": "claude-sonnet-4-6",
    "replan": "claude-sonnet-4-6",
    "issue_writer": "claude-sonnet-4-6",
    "issue_advisor": "claude-sonnet-4-6",
}

GOAL = """\
Implement the backend API for the Runsight GUI application.

ALL specifications are pre-written and reviewed. Read them in this order:

1. .agora/specs/api-architecture/coherence-check.md — START HERE. This is the
   lead architect's coherence report. It lists all resolved conflicts, the
   canonical decisions, coverage matrix, inter-spec dependency map, and the
   recommended implementation order.

2. .agora/specs/api-architecture/05-settings-schema.md — SQLite settings DB
   (providers, model_defaults, app_settings, fallback_chain tables).

3. .agora/specs/api-architecture/02-runs-model.md — Run persistence
   (workflow_runs, run_nodes, run_logs, runtime_audit tables) + RunObserver.

4. .agora/specs/api-architecture/04-realtime-events.md — WebSocket at
   /api/ws/events with channel subscriptions and event envelope.

5. .agora/specs/api-architecture/03-souls-api.md — Souls CRUD API with
   copy-on-edit, auto-discovery from filesystem.

6. .agora/specs/api-architecture/01-api-contract.md — Full REST API surface
   tying everything together (workflows, runs, souls, settings, git, runtime).

Context on the existing codebase:
- .agora/specs/api-architecture/_context.md has pointers to all relevant
  existing code, design docs, epics, and ADRs.
- The existing FastAPI app is at apps/cli/src/runsight/api.py.
- The core engine is at libs/core/src/runsight_core/ (primitives, workflow,
  runner, state, observer, yaml/schema).
- The GUI app skeleton is at apps/gui/ (Next.js/React).

Constraints:
- FastAPI backend, SQLite for persistence, filesystem for YAML.
- WebSocket for real-time events (NOT SSE).
- No authentication in this version.
- All new backend code goes under apps/cli/src/runsight/ (extending the
  existing API module).
- Do NOT modify libs/core/ unless a spec explicitly requires it.
- Write tests for all new endpoints and models.
"""

mode = sys.argv[1] if len(sys.argv) > 1 else "fresh"

if mode == "fresh":
    url = "http://localhost:8003/reasoners/build"
    data = {
        "goal": GOAL,
        "repo_path": "/Users/mikhail.rogov/Documents/github/runsight",
        "artifacts_dir": ".artifacts",
        "config": {
            "models": MODELS,
            "runtime": "claude_code",
            "enable_learning": True,
            "max_concurrent_issues": 3,
        },
    }
    print("Starting FRESH API backend build...")
elif mode == "resume":
    url = "http://localhost:8003/reasoners/resume_build"
    data = {
        "repo_path": "/Users/mikhail.rogov/Documents/github/runsight",
        "artifacts_dir": ".artifacts",
        "config": {
            "models": MODELS,
            "runtime": "claude_code",
            "enable_learning": True,
            "max_concurrent_issues": 3,
        },
    }
    print("RESUMING API backend build...")
else:
    print(f"Unknown mode: {mode}. Use 'fresh' or 'resume'.")
    sys.exit(1)

print(f"URL: {url}")
print(f"Models: default={MODELS['default']}, coder={MODELS['coder']}, pm={MODELS['pm']}")
print(f"Goal length: {len(GOAL)} chars")
print()

req = urllib.request.Request(
    url,
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=7200) as response:
        result = response.read().decode("utf-8")
        print(f"Build completed. Response:\n{result}")
except Exception as e:
    print(f"Error: {e}")
    if hasattr(e, "read"):
        print(e.read().decode("utf-8", errors="replace"))
