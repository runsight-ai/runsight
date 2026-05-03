from pathlib import Path

WORKFLOW_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "workflows"


def workflow_fixture_text(name: str) -> str:
    return (WORKFLOW_FIXTURE_DIR / name).read_text(encoding="utf-8")
