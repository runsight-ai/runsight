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
    "replan": "claude-sonnet-4-6",
    "issue_writer": "claude-sonnet-4-6",
}

mode = sys.argv[1] if len(sys.argv) > 1 else "resume"

if mode == "fresh":
    url = "http://localhost:8003/reasoners/build"
    data = {
        "goal": "Read and implement the full spec from .agora/adrs/phase-1.6a-workflow-block-adr.md. You MUST follow the instructions in .agora/swe-af/swe_af_1_6a_goal.md",
        "repo_path": "/Users/mikhail.rogov/Documents/github/runsight",
        "artifacts_dir": ".artifacts",
        "config": {"models": MODELS},
    }
    print("Starting FRESH build...")
elif mode == "resume":
    url = "http://localhost:8003/reasoners/resume_build"
    data = {
        "repo_path": "/Users/mikhail.rogov/Documents/github/runsight",
        "artifacts_dir": ".artifacts",
        "config": {"models": MODELS},
    }
    print("RESUMING from checkpoint...")
else:
    print(f"Unknown mode: {mode}. Use 'fresh' or 'resume'.")
    sys.exit(1)

req = urllib.request.Request(
    url,
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req) as response:
        print(f"{mode.title()} execution completed.")
except Exception as e:
    print(f"Error: {e}")
