"""
RED tests for RUN-907: define context audit contract and YAML access schema.

These tests pin the public contract surface expected by RUN-868:
- BaseBlockDef gains access with a declared default
- the context governance module exposes the audit and policy models
- context refs normalize into the supported namespaces
- invalid enums are rejected by Pydantic
- workflow-seeded inputs stay represented as results.workflow
"""

from datetime import UTC, datetime
from importlib import import_module

import pytest
from pydantic import ValidationError
from runsight_core.yaml.schema import BaseBlockDef


def _load_contract_module():
    return import_module("runsight_core.context_governance")


def test_base_block_def_defaults_access_to_declared():
    """A bare block definition defaults access to declared."""
    block = BaseBlockDef.model_validate({"type": "code"})

    assert block.access == "declared"
    assert block.model_dump()["access"] == "declared"


def test_base_block_def_accepts_explicit_all_access():
    """A block definition can explicitly opt into all access."""
    block = BaseBlockDef.model_validate({"type": "code", "access": "all"})

    assert block.access == "all"
    assert block.model_dump()["access"] == "all"


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

    assert "workflow_inputs" not in {member.value for member in cg.ContextAuditNamespace}


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
