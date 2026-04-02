"""Red tests for RUN-556: WorkflowEntity explicit enabled field.

These tests must FAIL because WorkflowEntity currently relies on
extra="allow" for the enabled field instead of having an explicit
`enabled: bool = False` field declaration.

AC covered:
  - WorkflowEntity has explicit enabled field
  - Default value is False
  - Field appears in model_fields (not just allowed via extra)
"""

from runsight_api.domain.value_objects import WorkflowEntity


class TestWorkflowEntityEnabledField:
    """WorkflowEntity must have an explicit `enabled: bool = False` field."""

    def test_enabled_is_declared_in_model_fields(self):
        """The 'enabled' field must be an explicit field declaration,
        not merely tolerated via extra='allow'."""
        assert "enabled" in WorkflowEntity.model_fields, (
            "WorkflowEntity must declare 'enabled' as an explicit field, not rely on extra='allow'"
        )

    def test_enabled_defaults_to_false(self):
        """A WorkflowEntity created without specifying enabled should default to False."""
        entity = WorkflowEntity(id="test-wf")
        assert entity.enabled is False

    def test_enabled_field_type_is_bool(self):
        """The enabled field annotation must be bool."""
        field_info = WorkflowEntity.model_fields["enabled"]
        assert field_info.annotation is bool, (
            f"Expected enabled field type to be bool, got {field_info.annotation}"
        )

    def test_enabled_true_roundtrips(self):
        """Setting enabled=True should persist through model construction."""
        assert "enabled" in WorkflowEntity.model_fields, (
            "WorkflowEntity must declare 'enabled' as an explicit field, not rely on extra='allow'"
        )
        entity = WorkflowEntity(id="test-wf", enabled=True)
        assert entity.enabled is True

    def test_enabled_false_roundtrips(self):
        """Setting enabled=False should persist through model construction."""
        assert "enabled" in WorkflowEntity.model_fields, (
            "WorkflowEntity must declare 'enabled' as an explicit field, not rely on extra='allow'"
        )
        entity = WorkflowEntity(id="test-wf", enabled=False)
        assert entity.enabled is False

    def test_enabled_appears_in_model_dump(self):
        """The enabled field must appear in model_dump output as a declared field."""
        assert "enabled" in WorkflowEntity.model_fields, (
            "WorkflowEntity must declare 'enabled' as an explicit field, not rely on extra='allow'"
        )
        entity = WorkflowEntity(id="test-wf", enabled=True)
        dumped = entity.model_dump()
        assert "enabled" in dumped
        assert dumped["enabled"] is True

    def test_enabled_in_model_json_schema(self):
        """The enabled field must appear in the JSON schema as a proper property."""
        schema = WorkflowEntity.model_json_schema()
        assert "enabled" in schema.get("properties", {}), (
            "enabled must be a declared property in the JSON schema"
        )
