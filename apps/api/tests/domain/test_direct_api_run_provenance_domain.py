"""Direct API run provenance domain contracts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from sqlmodel import Session, SQLModel, create_engine

COMMITTED_MAIN_SHA = "abc123def4567890abc123def4567890abc123de"


def _make_run(**overrides):
    from runsight_api.domain.entities.run import Run

    values = {
        "id": "direct-provenance-provenance",
        "workflow_id": "wf-direct-provenance",
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


def _deferred_persistence_hits(names: set[str]) -> list[str]:
    """Find deferred persistence names while allowing existing token metrics."""
    allowed_token_metrics = {"tokens", "total_tokens"}
    deferred_terms = (
        "webhook",
        "schedule",
        "scheduler",
        "trigger",
        "delivery",
        "idempotency",
    )
    hits = []
    for name in sorted(names):
        lowered = name.lower()
        if any(term in lowered for term in deferred_terms):
            hits.append(name)
        elif "token" in lowered and lowered not in allowed_token_metrics:
            hits.append(name)
    return hits


def _migration_identifiers(source: str) -> set[str]:
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", source))


def _mock_run(
    run_id: str,
    *,
    source: str,
    branch: str = "main",
    created_at: float,
):
    run = Mock()
    run.id = run_id
    run.workflow_id = "wf-direct-provenance"
    run.workflow_name = "Direct API Workflow"
    run.source = source
    run.branch = branch
    run.created_at = created_at
    return run


def _mock_node(
    run_id: str,
    *,
    eval_passed: bool,
):
    node = Mock()
    node.node_id = "shared_node"
    node.run_id = run_id
    node.soul_id = "researcher"
    node.soul_version = "sha256:direct-provenance"
    node.eval_score = 0.9
    node.eval_passed = eval_passed
    node.cost_usd = 0.01
    node.tokens = {"prompt": 100, "completion": 50, "total": 150}
    node.created_at = 100.0
    return node


class TestDirectApiProvenanceMigrationContract:
    def test_migration_adds_direct_api_provenance_columns_and_indexes_only(self) -> None:
        """Direct API provenance migration must add provenance without deferred trigger/idempotency storage."""
        all_migration_sources = _migration_sources()
        provenance_migrations = [
            (path, source)
            for path, source in all_migration_sources
            if "source_metadata" in source or "source_correlation_id" in source
        ]
        assert provenance_migrations, "Expected a migration for direct API provenance"

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

        all_migration_identifiers = set()
        for _, source in all_migration_sources:
            all_migration_identifiers.update(_migration_identifiers(source))
        deferred_hits = _deferred_persistence_hits(all_migration_identifiers)
        assert deferred_hits == [], (
            "Direct API provenance migration surface must not include deferred persistence identifiers: "
            f"{deferred_hits}"
        )


class TestDirectApiProvenancePersistenceContract:
    def test_provenance_fields_exist_without_deferred_persistence_surfaces(self) -> None:
        """Direct API provenance must exist without webhook/schedule/idempotency persistence."""
        from runsight_api.domain.entities.run import Run
        from runsight_api.transport.schemas.runs import RunResponse

        run_model_fields = set(Run.model_fields)
        run_table_columns = {column.name for column in Run.__table__.columns}
        response_fields = set(RunResponse.model_fields)

        required_provenance_fields = {"source_metadata", "source_correlation_id"}
        assert required_provenance_fields.issubset(run_model_fields)
        assert required_provenance_fields.issubset(run_table_columns)
        assert required_provenance_fields.issubset(response_fields)

        all_surface_names = run_model_fields | run_table_columns | response_fields
        deferred_hits = _deferred_persistence_hits(all_surface_names)
        assert deferred_hits == []


class TestDirectApiRunEntityProvenance:
    def test_api_run_persists_committed_main_identity_and_safe_metadata(self) -> None:
        """API runs should round-trip source='api', committed main identity, and safe provenance."""
        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)
        safe_metadata = {
            "entry_path": "direct_api",
            "request_path": "/api/workflows/wf-direct-provenance/invocations",
            "client_request_id": "req-direct-provenance",
        }

        with Session(engine) as session:
            session.add(
                _make_run(
                    id="direct-provenance-api",
                    source_metadata=safe_metadata,
                    source_correlation_id="corr-direct-provenance",
                )
            )
            session.commit()

        with Session(engine) as session:
            from runsight_api.domain.entities.run import Run

            loaded = session.get(Run, "direct-provenance-api")

        assert loaded is not None
        assert loaded.source == "api"
        assert loaded.branch == "main"
        assert loaded.commit_sha == COMMITTED_MAIN_SHA
        assert loaded.source_correlation_id == "corr-direct-provenance"
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


class TestDirectApiRunResponseProvenance:
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
            workflow_id="wf-direct-provenance",
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
            source_correlation_id="corr-direct-provenance",
            source_metadata={
                "entry_path": "direct_api",
                "client_request_id": "req-direct-provenance",
            },
        )

        payload = response.model_dump()
        serialized = json.dumps(payload, sort_keys=True)

        assert payload["source"] == "api"
        assert payload["branch"] == "main"
        assert payload["commit_sha"] == COMMITTED_MAIN_SHA
        assert payload["source_correlation_id"] == "corr-direct-provenance"
        assert payload["source_metadata"] == {
            "entry_path": "direct_api",
            "client_request_id": "req-direct-provenance",
        }
        assert "idempotency" not in serialized.lower()


class TestDirectApiProductionSourceSemantics:
    def test_api_main_run_is_production_baseline_and_simulation_between_runs_is_not(self) -> None:
        """Downstream regression logic must include API production runs and exclude simulations."""
        from runsight_api.logic.services.eval_service import EvalService

        repo = Mock()
        manual_baseline = _mock_run(
            "run-manual-pass",
            source="manual",
            created_at=100.0,
        )
        api_baseline = _mock_run(
            "run-api-fail",
            source="api",
            created_at=200.0,
        )
        simulation_between = _mock_run(
            "run-simulation-pass",
            source="simulation",
            branch="sim/direct-provenance",
            created_at=300.0,
        )
        current_manual = _mock_run(
            "run-manual-current-fail",
            source="manual",
            created_at=400.0,
        )

        nodes_by_run = {
            "run-manual-pass": [_mock_node("run-manual-pass", eval_passed=True)],
            "run-api-fail": [_mock_node("run-api-fail", eval_passed=False)],
            "run-simulation-pass": [_mock_node("run-simulation-pass", eval_passed=True)],
            "run-manual-current-fail": [_mock_node("run-manual-current-fail", eval_passed=False)],
        }
        repo.get_run.return_value = current_manual
        repo.list_runs.return_value = [
            current_manual,
            simulation_between,
            api_baseline,
            manual_baseline,
        ]
        repo.list_nodes_for_run.side_effect = lambda run_id: nodes_by_run[run_id]

        result = EvalService(repo).get_run_regressions("run-manual-current-fail")

        assert result == {"count": 0, "issues": []}
