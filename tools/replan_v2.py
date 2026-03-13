import requests


def trigger_replan():
    print("Triggering Architecture Replan...")
    try:
        response = requests.post(
            "http://localhost:8004/reasoners/architect",
            json={
                "prd": {"content": "Refer to .artifacts/plan/prd.md"},
                "repo_path": "/Users/mikhail.rogov/Documents/github/runsight",
                "artifacts_dir": ".artifacts",
                "feedback": "Tech lead rejected the architecture due to 4 blocking issues: Type Safety Violation in Workflow.run(), Input Mapping issues, etc. Fix these blockers.",
                "model": "claude-sonnet-4-6",
                "permission_mode": "bypassPermissions",
                "ai_provider": "claude",
                "workspace_manifest": None,
            },
        )
        print("Status:", response.status_code)
        print("Response:", response.text)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    trigger_replan()
