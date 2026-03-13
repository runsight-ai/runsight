import requests


def trigger_replanner():
    print("Triggering Replanner...")
    try:
        response = requests.post(
            "http://localhost:8004/reasoners/replan",
            json={
                "prd_path": "/Users/mikhail.rogov/Documents/github/runsight/.artifacts/plan/prd.md",
                "architecture_path": "/Users/mikhail.rogov/Documents/github/runsight/.artifacts/plan/architecture.md",
                "team_feedback": "/Users/mikhail.rogov/Documents/github/runsight/.artifacts/plan/tech_lead_feedback.txt",
            },
        )
        print("Status:", response.status_code)
        print("Response:", response.text)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    trigger_replanner()
