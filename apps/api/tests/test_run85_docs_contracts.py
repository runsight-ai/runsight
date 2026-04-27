from pathlib import Path


def test_cli_reference_docker_override_preserves_container_host_bind() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    cli_reference = repo_root / "apps/site/src/content/docs/docs/reference/cli-reference.md"

    text = cli_reference.read_text(encoding="utf-8")

    assert "runsight --host 0.0.0.0 --port 3000" in text


def test_direct_api_docs_require_committed_main_and_enabled_workflows() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    direct_api_reference = (
        repo_root / "apps/site/src/content/docs/docs/reference/direct-api-invocation.md"
    )
    running_workflows = repo_root / "apps/site/src/content/docs/docs/execution/running-workflows.md"

    reference_text = direct_api_reference.read_text(encoding="utf-8")
    running_text = running_workflows.read_text(encoding="utf-8")

    assert "committed `main` workflow snapshot and requires `enabled: true`" in reference_text
    assert "Omitting `enabled` is treated the same as `enabled: false`" in reference_text
    assert "committed on `main` and explicitly enabled with `enabled: true`" in running_text
