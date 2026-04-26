"""RED tests for RUN-930 direct API run provenance foundation."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlmodel import Session, SQLModel, create_engine

COMMITTED_MAIN_SHA = "abc123def4567890abc123def4567890abc123de"


def _make_run(**overrides):
    from runsight_api.domain.entities.run import Run

    values = {
        "id": "run-930-provenance",
        "workflow_id": "wf-930",
        "workflow_name": "Direct API Workflow",
        "task_json": "{}",
        "branch": "main",
        "source": "api",
        "commit_sha": COMMITTED_MAIN_SHA,
    }
    values.update(overrides)
    return Run(**values)


def _versions_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "src" / "runsight_api" / "alembic" / "versions"


def _migration_sources() -> list[tuple[Path, str]]:
    return [
        (path, path.read_text())
        for path in sorted(_versions_dir().glob("*.py"))
        if path.name != "__init__.py"
    ]


class TestRun930AlembicMigrationContract:
    def test_migration_adds_direct_api_provenance_columns_and_indexes_only(self) -> None:
        """RUN-930 must add direct API provenance without deferred trigger/idempotency storage."""
        provenance_migrations = [
            (path, source)
            for path, source in _migration_sources()
            if "source_metadata" in source or "source_correlation_id" in source
        ]
        assert provenance_migrations, "Expected a RUN-930 migration for direct API provenance"

        combined = "\n".join(source for _, source in provenance_migrations)
        assert "source_metadata" in combined
        assert "source_correlation_id" in combined
        assert re.search(r"source_metadata.+JSON|JSON.+source_metadata", combined, re.DOTALL)
        assert "nullable=True" in combined

        normalized = re.sub(r"\s+", "", combined)
        assert re.search(
            r"create_index\([^)]*\[.*['\"]source['\"].*['\"]created_at['\"].*\]",
            normalized,
        ), "Expected an index over (source, created_at)"
        assert re.search(
            r"create_index\([^)]*\[.*['\"]workflow_id['\"].*['\"]source['\"].*['\"]created_at['\"].*\]",
            normalized,
        ), "Expected an index over (workflow_id, source, created_at)"

        forbidden_terms = {
            "idempotency_key",
            "webhook",
            "schedule",
            "scheduler",
            "trigger",
            "delivery",
            "token",
        }
        found = {term for term in forbidden_terms if term in combined.lower()}
        assert not found, (
            f"RUN-930 migration must not include deferred persistence: {sorted(found)}"
        )


class TestRun930RunEntityProvenance:
    def test_api_run_persists_committed_main_identity_and_safe_metadata(self) -> None:
        """API runs should round-trip source='api', committed main identity, and safe provenance."""
        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)
        safe_metadata = {
            "entry_path": "direct_api",
            "request_path": "/api/workflows/wf-930/invocations",
            "client_request_id": "req-930",
        }

        with Session(engine) as session:
            session.add(
                _make_run(
                    id="run-930-api",
                    source_metadata=safe_metadata,
                    source_correlation_id="corr-930",
                )
            )
            session.commit()

        with Session(engine) as session:
            from runsight_api.domain.entities.run import Run

            loaded = session.get(Run, "run-930-api")

        assert loaded is not None
        assert loaded.source == "api"
        assert loaded.branch == "main"
        assert loaded.commit_sha == COMMITTED_MAIN_SHA
        assert loaded.source_correlation_id == "corr-930"
        assert loaded.source_metadata == safe_metadata

    @pytest.mark.parametrize(
        "unsafe_metadata",
        [
            {"headers": {"authorization": "Bearer secret"}},
            {"authorization": "Bearer secret"},
            {"raw_body": {"inputs": {"api_token": "secret"}}},
            {"inputs": {"api_token": "secret"}},
            {"idempotency_key": "deferred-until-later-slice"},
        ],
    )
    def test_source_metadata_rejects_sensitive_or_deferred_payload_keys(
        self,
        unsafe_metadata: dict[str, object],
    ) -> None:
        """Provenance metadata must not persist raw request data or idempotency placeholders."""
        with pytest.raises(ValidationError):
            _make_run(source_metadata=unsafe_metadata)

    def test_source_metadata_rejects_oversized_payload(self) -> None:
        """The JSON provenance payload should have an intentional size boundary."""
        with pytest.raises(ValidationError):
            _make_run(source_metadata={"client_context": "x" * 8192})


class TestRun930RunResponseProvenance:
    def test_old_run_response_defaults_provenance_safely_and_preserves_unknown_source(self) -> None:
        """Old rows with missing provenance and unknown source strings must serialize safely."""
        from runsight_api.transport.schemas.runs import RunResponse

        response = RunResponse(
            id="run-legacy",
            workflow_id="wf-legacy",
            workflow_name="Legacy",
            status="completed",
            started_at=None,
            completed_at=None,
            duration_seconds=None,
            total_cost_usd=0.0,
            total_tokens=0,
            created_at=1711699200.0,
            branch="main",
            source="legacy-runner",
            commit_sha=None,
        )

        assert response.source == "legacy-runner"
        assert response.source_correlation_id is None
        assert response.source_metadata == {}

    def test_api_run_response_exposes_safe_provenance_without_idempotency(self) -> None:
        """Direct API responses may expose safe provenance but must not expose idempotency state."""
        from runsight_api.transport.schemas.runs import RunResponse

        response = RunResponse(
            id="run-api",
            workflow_id="wf-930",
            workflow_name="Direct API Workflow",
            status="pending",
            started_at=None,
            completed_at=None,
            duration_seconds=None,
            total_cost_usd=0.0,
            total_tokens=0,
            created_at=1711699300.0,
            branch="main",
            source="api",
            commit_sha=COMMITTED_MAIN_SHA,
            source_correlation_id="corr-930",
            source_metadata={"entry_path": "direct_api", "client_request_id": "req-930"},
        )

        payload = response.model_dump()
        serialized = json.dumps(payload, sort_keys=True)

        assert payload["source"] == "api"
        assert payload["branch"] == "main"
        assert payload["commit_sha"] == COMMITTED_MAIN_SHA
        assert payload["source_correlation_id"] == "corr-930"
        assert payload["source_metadata"] == {
            "entry_path": "direct_api",
            "client_request_id": "req-930",
        }
        assert "idempotency" not in serialized.lower()
