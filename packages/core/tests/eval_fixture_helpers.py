from pathlib import Path

EVAL_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "eval"


def eval_fixture_text(name: str) -> str:
    return (EVAL_FIXTURE_DIR / name).read_text(encoding="utf-8")
