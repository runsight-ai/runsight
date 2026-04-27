from pathlib import Path


def test_cli_reference_docker_override_preserves_container_host_bind() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    cli_reference = repo_root / "apps/site/src/content/docs/docs/reference/cli-reference.md"

    text = cli_reference.read_text(encoding="utf-8")

    assert "runsight --host 0.0.0.0 --port 3000" in text
