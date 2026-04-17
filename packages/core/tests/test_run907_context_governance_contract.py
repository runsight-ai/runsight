"""
RED tests for RUN-907: define context audit contract and YAML access schema.

These tests pin the public contract surface expected by RUN-868:
- BaseBlockDef must not expose public YAML access configuration
- the checked-in workflow schema stays aligned with the generated source of truth
- the context governance module exposes the audit and policy models
- context refs normalize into the supported namespaces
- invalid enums are rejected by Pydantic
- workflow-seeded inputs stay represented as results.workflow
"""

import json
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path

import pytest
from pydantic import ValidationError
from runsight_core.yaml.schema import BaseBlockDef

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "runsight-workflow-schema.json"


def _collect_access_key_paths(schema: object) -> list[str]:
    paths: list[str] = []

    def visit(node: object, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "access":
                    paths.append(path or "$")
                visit(value, f"{path}.{key}" if path else key)
        elif isinstance(node, list):
            for index, item in enumerate(node):
                visit(item, f"{path}[{index}]")

    visit(schema, "")
    return paths


def _load_contract_module():
    return import_module("runsight_core.context_governance")


def test_base_block_def_hides_access_from_public_yaml_dump():
    """A bare block definition must not serialize access in public YAML."""
    block = BaseBlockDef.model_validate({"type": "code"})

    assert "access" not in block.model_dump()


def test_base_block_def_rejects_public_access_declared_field():
    """A block definition must reject access: declared as unsupported public YAML."""
    with pytest.raises(ValidationError):
        BaseBlockDef.model_validate({"type": "code", "access": "declared"})


def test_base_block_def_rejects_explicit_all_access():
    """A block definition must reject access: all as unsupported configuration."""
    with pytest.raises(ValidationError):
        BaseBlockDef.model_validate({"type": "code", "access": "all"})


def test_context_governance_module_exports_expected_contract():
    """The runtime governance module exposes the expected contract surface."""
    cg = _load_contract_module()

    expected_names = {
        "ContextAuditEventV1",
        "ContextAuditRecordV1",
        "ContextGovernancePolicy",
        "ContextAccess",
        "ContextAuditNamespace",
        "ContextAuditMode",
        "ContextAuditStatus",
        "ContextAuditSeverity",
        "ParsedContextRef",
        "parse_context_ref",
    }

    for name in expected_names:
        assert hasattr(cg, name), f"missing contract symbol: {name}"

    assert {member.value for member in cg.ContextAuditNamespace} == {
        "results",
        "shared_memory",
        "metadata",
    }
    assert {member.value for member in cg.ContextAuditMode} == {"strict", "dev"}
    assert {member.value for member in cg.ContextAuditStatus} == {
        "resolved",
        "missing",
        "denied",
        "empty",
    }
    assert {member.value for member in cg.ContextAccess} == {"declared"}
    assert {member.value for member in cg.ContextAuditSeverity} == {
        "allow",
        "warn",
        "error",
    }
    assert "workflow_inputs" not in {member.value for member in cg.ContextAuditNamespace}


def test_context_governance_policy_defaults_to_strict():
    """A default policy must stay strict unless explicitly overridden."""
    cg = _load_contract_module()

    policy = cg.ContextGovernancePolicy()

    assert policy.mode == "strict"
    assert policy.model_dump()["mode"] == "strict"


def test_parse_context_ref_supports_explicit_and_unqualified_refs():
    """Context refs normalize results, shared_memory, and metadata paths."""
    cg = _load_contract_module()

    parsed = cg.parse_context_ref("shared_memory.customer.id")
    assert parsed.namespace == "shared_memory"
    assert parsed.source == "customer"
    assert parsed.field_path == "id"

    workflow_seeded = cg.parse_context_ref("workflow.output")
    assert workflow_seeded.namespace == "results"
    assert workflow_seeded.source == "workflow"
    assert workflow_seeded.field_path == "output"


def test_context_audit_event_serializes_workflow_seeded_input_in_results_namespace():
    """Workflow-seeded audit records serialize under results.workflow."""
    cg = _load_contract_module()

    record = cg.ContextAuditRecordV1(
        input_name="draft",
        from_ref="workflow.output",
        namespace="results",
        source="workflow",
        field_path="output",
        status="resolved",
        severity="allow",
        value_type="str",
        preview='"hello"',
        reason=None,
        internal=False,
    )
    event = cg.ContextAuditEventV1(
        schema_version="context_audit.v1",
        event="context_resolution",
        run_id="run_123",
        workflow_name="example_workflow",
        node_id="node_1",
        block_type="code",
        access="declared",
        mode="strict",
        records=[record],
        resolved_count=1,
        denied_count=0,
        warning_count=0,
        emitted_at=datetime(2026, 4, 16, tzinfo=UTC),
    )

    payload = event.model_dump()
    assert payload["records"][0]["namespace"] == "results"
    assert payload["records"][0]["source"] == "workflow"
    assert "workflow_inputs" not in payload["records"][0]

    round_tripped = cg.ContextAuditEventV1.model_validate(payload)
    assert round_tripped == event


def test_context_audit_event_sequence_defaults_to_none_and_round_trips_integer_values():
    """ContextAuditEventV1 should default sequence to None and preserve explicit integers."""
    cg = _load_contract_module()

    base_kwargs = dict(
        schema_version="context_audit.v1",
        event="context_resolution",
        run_id="run_123",
        workflow_name="example_workflow",
        node_id="node_1",
        block_type="code",
        access="declared",
        mode="strict",
        records=[],
        resolved_count=0,
        denied_count=0,
        warning_count=0,
        emitted_at=datetime(2026, 4, 16, tzinfo=UTC),
    )

    default_event = cg.ContextAuditEventV1(**base_kwargs)
    assert default_event.sequence is None
    assert default_event.model_dump()["sequence"] is None

    sequenced_event = cg.ContextAuditEventV1(sequence=17, **base_kwargs)
    assert sequenced_event.sequence == 17
    assert sequenced_event.model_dump()["sequence"] == 17


def test_context_audit_event_rejects_missing_or_none_workflow_name():
    """workflow_name must be required and non-null on ContextAuditEventV1."""
    cg = _load_contract_module()

    base_kwargs = dict(
        schema_version="context_audit.v1",
        event="context_resolution",
        run_id="run_123",
        node_id="node_1",
        block_type="code",
        access="declared",
        mode="strict",
        records=[],
        resolved_count=0,
        denied_count=0,
        warning_count=0,
        emitted_at=datetime(2026, 4, 16, tzinfo=UTC),
    )

    with pytest.raises(ValidationError):
        cg.ContextAuditEventV1.model_validate(base_kwargs)

    with pytest.raises(ValidationError):
        cg.ContextAuditEventV1.model_validate({**base_kwargs, "workflow_name": None})


def test_context_audit_record_rejects_all_access_status():
    """Audit records must not expose the historical all_access status."""
    cg = _load_contract_module()

    with pytest.raises(ValidationError):
        cg.ContextAuditRecordV1(
            input_name=None,
            from_ref=None,
            namespace=None,
            source=None,
            field_path=None,
            status="all_access",
            severity="allow",
            value_type=None,
            preview=None,
            reason="all access",
            internal=False,
        )

    record = cg.ContextAuditRecordV1(
        input_name=None,
        from_ref=None,
        namespace=None,
        source=None,
        field_path=None,
        status="empty",
        severity="allow",
        value_type=None,
        preview=None,
        reason=None,
        internal=False,
    )

    payload = record.model_dump()
    assert payload["input_name"] is None
    assert payload["from_ref"] is None
    assert payload["namespace"] is None
    assert payload["source"] is None
    assert payload["field_path"] is None


def test_dev_mode_warns_without_exposing_undeclared_data():
    """Dev mode can warn on denied access without leaking the denied value."""
    cg = _load_contract_module()

    policy = cg.ContextGovernancePolicy(mode="dev")
    record = cg.ContextAuditRecordV1(
        input_name="secret",
        from_ref="shared_memory.customer.ssn",
        namespace="shared_memory",
        source="customer",
        field_path="ssn",
        status="denied",
        severity="warn",
        value_type=None,
        preview=None,
        reason="undeclared access",
        internal=False,
    )
    event = cg.ContextAuditEventV1(
        schema_version="context_audit.v1",
        event="context_resolution",
        run_id="run_123",
        workflow_name="example_workflow",
        node_id="node_1",
        block_type="code",
        access="declared",
        mode=policy.mode,
        records=[record],
        resolved_count=0,
        denied_count=1,
        warning_count=1,
        emitted_at=datetime(2026, 4, 16, tzinfo=UTC),
    )

    payload = event.model_dump()
    assert policy.mode == "dev"
    assert payload["mode"] == "dev"
    assert payload["records"][0] == {
        "input_name": "secret",
        "from_ref": "shared_memory.customer.ssn",
        "namespace": "shared_memory",
        "source": "customer",
        "field_path": "ssn",
        "status": "denied",
        "severity": "warn",
        "value_type": None,
        "preview": None,
        "reason": "undeclared access",
        "internal": False,
    }


def test_context_audit_event_rejects_invalid_schema_and_event_literals():
    """Invalid literal values for the event contract must fail validation."""
    cg = _load_contract_module()

    base_kwargs = dict(
        run_id="run_123",
        workflow_name="example_workflow",
        node_id="node_1",
        block_type="code",
        access="declared",
        mode="strict",
        records=[],
        resolved_count=0,
        denied_count=0,
        warning_count=0,
        emitted_at=datetime(2026, 4, 16, tzinfo=UTC),
    )

    with pytest.raises(ValidationError):
        cg.ContextAuditEventV1(
            schema_version="context_audit.v2", event="context_resolution", **base_kwargs
        )

    with pytest.raises(ValidationError):
        cg.ContextAuditEventV1(
            schema_version="context_audit.v1", event="context_changed", **base_kwargs
        )


def test_base_block_def_rejects_invalid_access_values():
    """BaseBlockDef must reject unknown access values."""
    with pytest.raises(ValidationError):
        BaseBlockDef.model_validate({"type": "code", "access": "restricted"})


def test_checked_in_workflow_schema_does_not_expose_access_keys_or_enums():
    """The published workflow schema must not leak public access configuration."""
    schema = json.loads(SCHEMA_PATH.read_text())
    access_enum_values: set[str] = set()

    def visit(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "enum" and isinstance(value, list):
                    access_enum_values.update(str(item) for item in value)
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(schema)

    assert _collect_access_key_paths(schema) == []
    assert "declared" not in access_enum_values
    assert "all" not in access_enum_values


def test_checked_in_workflow_schema_matches_generated_schema_without_access():
    """The checked-in workflow schema should track the generated source of truth."""
    from runsight_core.yaml.schema import RunsightWorkflowFile

    schema = json.loads(SCHEMA_PATH.read_text())
    generated = RunsightWorkflowFile.model_json_schema()

    assert _collect_access_key_paths(schema) == _collect_access_key_paths(generated) == []


def test_context_audit_event_redacts_secret_like_previews_but_keeps_normal_previews():
    """Secret-like previews must not serialize raw values, but normal previews may."""
    cg = _load_contract_module()

    secret_record = cg.ContextAuditRecordV1(
        input_name="api_key",
        from_ref="shared_memory.credentials.api_key",
        namespace="shared_memory",
        source="credentials",
        field_path="api_key",
        status="denied",
        severity="warn",
        value_type="str",
        preview="sk-live-secret",
        reason="secret-like value",
        internal=False,
    )
    normal_record = cg.ContextAuditRecordV1(
        input_name="summary",
        from_ref="results.workflow.summary",
        namespace="results",
        source="workflow",
        field_path="summary",
        status="resolved",
        severity="allow",
        value_type="str",
        preview="plain text preview",
        reason=None,
        internal=False,
    )

    secret_payload = secret_record.model_dump()
    normal_payload = normal_record.model_dump()

    assert secret_payload["preview"] != "sk-live-secret"
    assert isinstance(secret_payload["preview"], str)
    assert (
        "redact" in secret_payload["preview"].lower() or secret_payload["preview"] == "[redacted]"
    )
    assert normal_payload["preview"] == "plain text preview"


def test_invalid_context_audit_enums_are_rejected():
    """Invalid enum values should fail validation."""
    cg = _load_contract_module()

    with pytest.raises(ValidationError):
        cg.ContextAuditRecordV1(
            input_name="draft",
            from_ref="results.workflow.output",
            namespace="workflow_inputs",
            source="workflow",
            field_path="output",
            status="resolved",
            severity="allow",
            value_type="str",
            preview=None,
            reason=None,
        )

    with pytest.raises(ValidationError):
        cg.ContextGovernancePolicy(mode="permissive")
