"""RED tests for RUN-944 trigger runtime exposure configuration."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml


def test_settings_defaults_keep_no_auth_runtime_local_first() -> None:
    from runsight_api.core.config import Settings

    settings = Settings()

    assert settings.host == "127.0.0.1"
    assert settings.external_invocation_enabled is True
    assert settings.public_base_url is None
    assert settings.external_invocation_body_limit_bytes == 1_048_576
    assert settings.max_concurrent_runs > 0
    assert settings.max_pending_external_invocations > 0


def test_public_base_url_is_absent_by_default_and_explicit_when_configured() -> None:
    from runsight_api.core.config import Settings

    default_settings = Settings()
    explicit_settings = Settings(public_base_url="https://runs.example.com")

    assert default_settings.public_base_url is None
    assert str(explicit_settings.public_base_url).rstrip("/") == "https://runs.example.com"


def test_cli_default_host_is_loopback(monkeypatch) -> None:
    import uvicorn
    from runsight_api import cli

    captured: dict[str, object] = {}

    def fake_run(app_ref: str, *, host: str, port: int) -> None:
        captured.update({"app_ref": app_ref, "host": host, "port": port})

    monkeypatch.setattr(sys, "argv", ["runsight"])
    monkeypatch.setattr(uvicorn, "run", fake_run)

    cli.main()

    assert captured == {
        "app_ref": "runsight_api.main:app",
        "host": "127.0.0.1",
        "port": 8000,
    }


def test_cli_help_documents_loopback_default(monkeypatch, capsys) -> None:
    from runsight_api import cli

    monkeypatch.setattr(sys, "argv", ["runsight", "--help"])

    try:
        cli.main()
    except SystemExit as exc:
        assert exc.code == 0

    help_text = capsys.readouterr().out
    assert "default: 127.0.0.1" in help_text
    assert "default: 0.0.0.0" not in help_text


def _compose_port_binding(raw_port: object) -> dict[str, object]:
    if isinstance(raw_port, dict):
        return {
            "host_ip": raw_port.get("host_ip"),
            "published": str(raw_port.get("published")),
            "target": str(raw_port.get("target")),
        }
    if isinstance(raw_port, str):
        parts = raw_port.split(":")
        if len(parts) == 3:
            host_ip, published, target = parts
        elif len(parts) == 2:
            host_ip, published, target = None, parts[0], parts[1]
        else:
            host_ip, published, target = None, None, parts[-1]
        return {"host_ip": host_ip, "published": published, "target": target}
    raise AssertionError(f"Unsupported Docker Compose port binding: {raw_port!r}")


def test_docker_compose_and_runtime_defaults_preserve_loopback_port_binding() -> None:
    from runsight_api.core.config import Settings

    repo_root = Path(__file__).resolve().parents[3]
    compose_text = (repo_root / "docker-compose.yml").read_text(encoding="utf-8")
    dockerfile_text = (repo_root / "Dockerfile").read_text(encoding="utf-8")
    compose: dict[str, Any] = yaml.safe_load(compose_text)
    ports = compose["services"]["runsight"]["ports"]
    bindings = [_compose_port_binding(port) for port in ports]
    api_bindings = [
        binding
        for binding in bindings
        if binding["published"] == "8000" and binding["target"] == "8000"
    ]

    assert api_bindings, "runsight service must publish container port 8000 for local API use"
    assert any(binding["host_ip"] in {"127.0.0.1", "localhost"} for binding in api_bindings)
    assert not any(binding["host_ip"] in {None, "", "0.0.0.0", "::"} for binding in api_bindings)
    assert Settings().host == "127.0.0.1"
    assert 'CMD ["runsight", "--host", "0.0.0.0"]' in dockerfile_text
