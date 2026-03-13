import urllib.request
import json

url = "http://localhost:8004/reasoners/plan"
data = {
    "repo_path": "/Users/mikhail.rogov/Documents/github/runsight",
    "goal": "Read and implement the full spec from .agora/adrs/phase-1.6a-workflow-block-adr.md. You MUST follow the instructions in .agora/swe-af/swe_af_1_6a_goal.md",
    "plan_model": "claude-sonnet-4-6",
    "worker_model": "claude-haiku-4-5-20251001",
}

req = urllib.request.Request(
    url,
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req) as response:
        print(response.read().decode("utf-8"))
except Exception as e:
    print(e)
    # let's try the other common endpoint
    url = "http://localhost:8004/reasoners"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as response:
            print(response.read().decode("utf-8"))
    except Exception as e2:
        print(e2)
