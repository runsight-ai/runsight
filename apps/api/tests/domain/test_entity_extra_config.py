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
            SoulEntity(id="s1", role="Alpha", custom_notes="oops")

    def test_typo_field_is_rejected(self):
        with pytest.raises(ValidationError):
            SoulEntity(id="s1", naem="typo")

    def test_legacy_assertions_field_is_rejected(self):
        with pytest.raises(ValidationError):
            SoulEntity(
                id="s1",
                role="Tester",
                assertions=[{"type": "contains", "value": "hello"}],
            )

    def test_known_fields_work(self):
        soul = SoulEntity(
            id="s1",
            role="Alpha",
            system_prompt="Prompt",
            model_name="gpt-4o",
            tools=["web_search"],
            max_tool_iterations=7,
        )
        assert soul.id == "s1"
        assert soul.role == "Alpha"
        assert soul.system_prompt == "Prompt"
        assert soul.model_name == "gpt-4o"
        assert soul.tools == ["web_search"]
        assert soul.max_tool_iterations == 7


class TestProviderEntityRejectsExtraFields:
    def test_unknown_field_is_rejected(self):
        with pytest.raises(ValidationError):
            ProviderEntity(
                id="openai",
                name="OpenAI",
                type="openai",
                custom_notes="unsupported",
            )

    def test_typo_field_is_rejected(self):
        with pytest.raises(ValidationError):
            ProviderEntity(id="openai", name="OpenAI", tpye="openai")

    def test_known_fields_work(self):
        provider = ProviderEntity(
            id="openai",
            name="OpenAI",
            type="openai",
            api_key="${OPENAI_API_KEY}",
            base_url="https://api.openai.com/v1",
            is_active=True,
            status="connected",
            models=["gpt-4o"],
        )
        assert provider.id == "openai"
        assert provider.name == "OpenAI"
        assert provider.type == "openai"
        assert provider.models == ["gpt-4o"]


class TestWorkflowEntityPreservesExtraFields:
    def test_unknown_field_is_preserved(self):
        wf = WorkflowEntity(id="wf1", name="Pipeline", custom_meta="keep-me")
        assert hasattr(wf, "custom_meta")
        assert wf.custom_meta == "keep-me"

    def test_known_fields_work(self):
        wf = WorkflowEntity(id="wf1", name="Pipeline")
        assert wf.id == "wf1"
        assert wf.name == "Pipeline"


class TestWorkflowEntityWarningsField:
    def test_warnings_is_an_explicit_field_with_a_list_default(self):
        assert "warnings" in WorkflowEntity.model_fields

        field_info = WorkflowEntity.model_fields["warnings"]
        assert field_info.default_factory is list

        wf = WorkflowEntity(id="wf1")
        assert wf.warnings == []

    def test_warnings_preserve_explicit_payloads(self):
        warnings = [
            {
                "message": "Tool definition warning",
                "source": "tool_definitions",
                "context": "lookup_profile",
            }
        ]

        wf = WorkflowEntity(id="wf1", warnings=warnings)

        assert wf.warnings == warnings
