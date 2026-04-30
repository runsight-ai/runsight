"""Tests for entity extra-field schema strictness."""

import pytest
from pydantic import ValidationError

from runsight_api.domain.value_objects import (
    ProviderEntity,
    SoulEntity,
    WorkflowEntity,
)


class TestSoulEntityRejectsExtraFields:
    def test_unknown_field_is_rejected(self):
        with pytest.raises(ValidationError):
            SoulEntity(id="soul-alpha", kind="soul", name="Alpha", custom_notes="oops")

    def test_typo_field_is_rejected(self):
        with pytest.raises(ValidationError):
            SoulEntity(id="soul-alpha", kind="soul", name="Alpha", naem="typo")

    def test_legacy_assertions_field_is_rejected(self):
        with pytest.raises(ValidationError):
            SoulEntity(
                id="soul-alpha",
                kind="soul",
                name="Alpha",
                role="Tester",
                assertions=[{"type": "contains", "value": "hello"}],
            )

    def test_known_fields_work(self):
        soul = SoulEntity(
            id="soul-alpha",
            kind="soul",
            name="Alpha",
            role="Alpha",
            system_prompt="Prompt",
            model_name="fixture-soul-model",
            tools=["web_search"],
            max_tool_iterations=7,
        )
        assert soul.id == "soul-alpha"
        assert soul.role == "Alpha"
        assert soul.system_prompt == "Prompt"
        assert soul.model_name == "fixture-soul-model"
        assert soul.tools == ["web_search"]
        assert soul.max_tool_iterations == 7


class TestProviderEntityRejectsExtraFields:
    def test_unknown_field_is_rejected(self):
        with pytest.raises(ValidationError):
            ProviderEntity(
                id="fixture-provider",
                kind="provider",
                name="Fixture Provider",
                type="fixture-provider",
                custom_notes="unsupported",
            )

    def test_typo_field_is_rejected(self):
        with pytest.raises(ValidationError):
            ProviderEntity(
                id="fixture-provider",
                kind="provider",
                name="Fixture Provider",
                tpye="fixture-provider",
            )

    def test_known_fields_work(self):
        provider = ProviderEntity(
            id="fixture-provider",
            kind="provider",
            name="Fixture Provider",
            type="fixture-provider",
            api_key="dummy-fixture-provider-key-ref",
            base_url="http://localhost/fixture-provider/v1",
            is_active=True,
            status="connected",
            models=["fixture-chat-model"],
        )
        assert provider.id == "fixture-provider"
        assert provider.name == "Fixture Provider"
        assert provider.type == "fixture-provider"
        assert provider.models == ["fixture-chat-model"]


class TestWorkflowEntityPreservesExtraFields:
    def test_unknown_field_is_preserved(self):
        wf = WorkflowEntity(
            kind="workflow",
            id="pipeline_workflow",
            name="Pipeline",
            custom_meta="keep-me",
        )
        assert hasattr(wf, "custom_meta")
        assert wf.custom_meta == "keep-me"

    def test_known_fields_work(self):
        wf = WorkflowEntity(kind="workflow", id="pipeline_workflow", name="Pipeline")
        assert wf.id == "pipeline_workflow"
        assert wf.name == "Pipeline"


class TestWorkflowEntityWarningsField:
    def test_warnings_is_an_explicit_field_with_a_list_default(self):
        assert "warnings" in WorkflowEntity.model_fields

        field_info = WorkflowEntity.model_fields["warnings"]
        assert field_info.default_factory is list

        wf = WorkflowEntity(kind="workflow", id="pipeline_workflow")
        assert wf.warnings == []

    def test_warnings_preserve_explicit_payloads(self):
        warnings = [
            {
                "message": "Tool definition warning",
                "source": "tool_definitions",
                "context": "lookup_profile",
            }
        ]

        wf = WorkflowEntity(kind="workflow", id="pipeline_workflow", warnings=warnings)

        assert wf.warnings == warnings
