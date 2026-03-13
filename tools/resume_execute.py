import asyncio
import json
import sys

# Add SWE-AF to path so we can import it
sys.path.insert(0, "/private/tmp/SWE-AF")

from swe_af.execution.schemas import ExecutionConfig


async def main():
    with open("/Users/mikhail.rogov/Documents/github/runsight/.artifacts/plan/review.json") as f:
        review = json.load(f)

    _plan_result = {
        "prd": {"validated_description": "Use existing"},
        "architecture": {"summary": "Use existing"},
        "tasks": [
            {"task_id": "issue-01", "name": "schema-extension", "description": "Add schema fields"},
            {"task_id": "issue-02", "name": "workflow-registry", "description": "Add registry"},
            {
                "task_id": "issue-03",
                "name": "workflow-block-implementation",
                "description": "Implement block",
            },
            {
                "task_id": "issue-04",
                "name": "recursion-guard-tests",
                "description": "Add recursion tests",
            },
            {
                "task_id": "issue-05",
                "name": "parser-integration",
                "description": "Add parser support",
            },
            {
                "task_id": "issue-06",
                "name": "workflow-run-extension",
                "description": "Update run method",
            },
            {"task_id": "issue-07", "name": "api-endpoints", "description": "Add APIs"},
            {
                "task_id": "issue-08",
                "name": "workflow-integration-test",
                "description": "Add integration test",
            },
        ],
        "review": review,
        "repo_path": "/Users/mikhail.rogov/Documents/github/runsight",
        "artifacts_dir": ".artifacts",
    }

    _config = ExecutionConfig()

    print("Starting execution...")
    # Actually wait, run_dag requires an execute_fn which is normally built by the app.
    # Let's just use the build reasoner which wraps everything perfectly.


if __name__ == "__main__":
    asyncio.run(main())
