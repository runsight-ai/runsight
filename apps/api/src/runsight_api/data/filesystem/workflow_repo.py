"""
Filesystem-backed workflow repository.

Writes valid RunsightWorkflowFile YAML to custom/workflows/ with atomic writes.
Canvas state is stored as a JSON sidecar in custom/workflows/.canvas/.

The workflow id is embedded in the YAML file and is the canonical identity.
"""

import io
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote

# Two YAML libraries are used intentionally:
#   - pyyaml (yaml_mod): fast, simple, used for read-only parsing (safe_load).
#   - ruamel.yaml (YAML): used for round-trip writes (patch_yaml_field, update)
#     because it preserves user comments and original formatting — pyyaml strips
#     both on serialisation.
import yaml as yaml_mod
from ruamel.yaml import YAML
from pydantic import ValidationError as PydanticValidationError
from runsight_core.identity import EntityKind, EntityRef, validate_entity_id
from runsight_core.yaml.discovery import SoulScanner, WorkflowScanner
from runsight_core.yaml.parser import (
    _validate_declared_tool_definitions,
    validate_workflow_call_contracts,
    validate_tool_governance,
)
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import RunsightWorkflowFile

from ...domain.errors import InputValidationError, WorkflowNotFound
from ...domain.value_objects import WorkflowEntity
from ._utils import atomic_write as _shared_atomic_write

logger = logging.getLogger(__name__)


def _workflow_ref(workflow_id: str) -> str:
    return str(EntityRef(EntityKind.WORKFLOW, workflow_id))


class WorkflowRepository:
    """Persists workflows as YAML files in custom/workflows/.

    Filename convention: {workflow_id}.yaml
    Canvas sidecar: .canvas/{workflow_id}.canvas.json
    """

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.workflows_dir = self.base_path / "custom" / "workflows"
        self.canvas_dir = self.workflows_dir / ".canvas"
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        self.canvas_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        """Write content to a file atomically via temp file + rename.

        Delegates to the shared utility in _utils.py.
        """
        _shared_atomic_write(path, content)

    def _get_path(self, workflow_id: str) -> Path:
        """Get the YAML file path for a workflow id."""
        decoded = unquote(workflow_id)
        if ".." in decoded or "/" in decoded or "\\" in decoded:
            raise ValueError(f"Invalid path traversal in id: {workflow_id!r}")
        result = self.workflows_dir / f"{workflow_id}.yaml"
        if not str(result.resolve()).startswith(str(self.workflows_dir.resolve())):
            raise ValueError("Path traversal detected: resolved path escapes base directory")
        return result

    def _canvas_path(self, stem: str) -> Path:
        return self.canvas_dir / f"{stem}.canvas.json"

    @staticmethod
    def _has_workflow_blocks(file_def: RunsightWorkflowFile) -> bool:
        return any(block_def.type == "workflow" for block_def in file_def.blocks.values())

    def build_runnable_workflow_registry(
        self,
        workflow_id: str,
        raw_yaml: str,
        *,
        git_ref: Optional[str] = None,
        git_service: Any = None,
    ) -> WorkflowRegistry:
        data = yaml_mod.safe_load(raw_yaml)
        if not isinstance(data, dict):
            raise ValueError("YAML content is not a mapping")

        root_file = RunsightWorkflowFile.model_validate(data)
        registry = WorkflowRegistry()
        workflow_scanner = WorkflowScanner(self.base_path)
        workflow_index = workflow_scanner.scan(
            git_ref=git_ref,
            git_service=git_service,
        )
        workflow_results_by_id = {
            result.entity_id: result
            for result in workflow_index.get_all()
            if result.entity_id is not None
        }

        validation_index: Dict[str, Tuple[Path, RunsightWorkflowFile]] = {}
        root_ref = root_file.id
        root_path = self._get_path(workflow_id).resolve()
        registry.register(root_ref, root_file)
        validation_index[root_ref] = (root_path, root_file)

        pending: List[RunsightWorkflowFile] = [root_file]
        loaded_paths = {str(root_path)}

        while pending:
            current_file = pending.pop()
            for block_def in current_file.blocks.values():
                if block_def.type != "workflow":
                    continue

                resolved_child = workflow_results_by_id.get(block_def.workflow_ref)
                if resolved_child is None:
                    continue

                child_path = resolved_child.path
                child_ref = str(child_path)
                if child_ref in loaded_paths:
                    continue

                loaded_paths.add(child_ref)
                child_id = resolved_child.entity_id
                registry.register(child_id, resolved_child.item)
                validation_index[child_id] = (child_path, resolved_child.item)
                pending.append(resolved_child.item)

        validate_workflow_call_contracts(
            root_file,
            base_dir=str(self.base_path),
            validation_index=validation_index,
            current_workflow_ref=root_ref,
        )
        return registry

    def _validate_yaml_content(
        self, workflow_id: str, raw_yaml: Optional[str]
    ) -> Tuple[bool, Optional[str], List[Dict[str, Optional[str]]]]:
        """Validate raw YAML string against RunsightWorkflowFile schema.

        Returns (valid, validation_error, warnings) — never raises.
        If raw_yaml is None or empty, returns (False, ...).
        """
        if not raw_yaml:
            return False, "No YAML content to validate", []
        warnings: List[Dict[str, Optional[str]]] = []
        try:
            data = yaml_mod.safe_load(raw_yaml)
            if not isinstance(data, dict):
                return False, "YAML content is not a mapping", []
            file_def = RunsightWorkflowFile.model_validate(data)
            souls_map = SoulScanner(self.base_path).scan().ids()
            validation_result = validate_tool_governance(file_def, souls_map)
            validation_result.merge(
                _validate_declared_tool_definitions(
                    file_def,
                    base_dir=str(self.base_path),
                    require_custom_metadata=True,
                )
            )
            warnings = validation_result.warnings_as_dicts()
            if validation_result.has_errors:
                return (
                    False,
                    validation_result.error_summary or "Tool governance validation failed",
                    warnings,
                )
            if self._has_workflow_blocks(file_def):
                try:
                    self.build_runnable_workflow_registry(workflow_id, raw_yaml)
                except ValueError as e:
                    return False, str(e), warnings
            return True, None, warnings
        except PydanticValidationError as e:
            return False, str(e), []
        except ValueError as e:
            return False, str(e), warnings
        except Exception as e:
            return False, f"Unexpected validation error: {e}", warnings

    def _write_canvas_sidecar(self, stem: str, canvas_state: Any) -> None:
        """Write the canvas sidecar JSON file."""
        if canvas_state is None:
            return
        # Convert pydantic model to dict if needed
        if hasattr(canvas_state, "model_dump"):
            canvas_data = canvas_state.model_dump()
        elif isinstance(canvas_state, dict):
            canvas_data = canvas_state
        else:
            logger.warning("Unexpected canvas_state type: %s", type(canvas_state))
            return
        try:
            content = json.dumps(canvas_data, indent=2, sort_keys=True)
            self._atomic_write(self._canvas_path(stem), content)
        except Exception as e:
            # D5: canvas write failure after YAML success is acceptable
            logger.warning("Failed to write canvas sidecar for %s: %s", stem, e)

    def _read_canvas_sidecar(self, stem: str) -> Optional[Dict[str, Any]]:
        """Read the canvas sidecar JSON file, if it exists."""
        path = self._canvas_path(stem)
        if not path.exists():
            return None
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to read canvas sidecar %s: %s", path, e)
            return None

    def _build_entity(
        self,
        data: Dict[str, Any],
        stem: str,
        canvas_state: Optional[Dict[str, Any]] = None,
        raw_yaml: Optional[str] = None,
    ) -> WorkflowEntity:
        """Build a WorkflowEntity from YAML data + canvas sidecar.

        Args:
            data: Parsed YAML data dict.
            stem: Filename stem used for the stored file.
            canvas_state: Optional canvas sidecar data.
            raw_yaml: Raw YAML file content (WYSIWYG). If None, the yaml
                      field in the entity will be None.
        """
        entity_id = data.get("id")
        if not isinstance(entity_id, str) or not entity_id:
            raise ValueError(f"{stem}.yaml: missing required id")
        if entity_id != stem:
            raise ValueError(
                f"{stem}.yaml: embedded id '{entity_id}' does not match filename stem '{stem}'"
            )

        # Validate the raw YAML content against RunsightWorkflowFile schema
        valid, validation_error, warnings = self._validate_yaml_content(stem, raw_yaml)

        entity_data = dict(data)
        entity_data["yaml"] = raw_yaml
        entity_data["valid"] = valid
        entity_data["validation_error"] = validation_error
        entity_data["warnings"] = warnings
        entity_data["filename"] = f"{stem}.yaml"
        if canvas_state is not None:
            entity_data["canvas_state"] = canvas_state

        # Extract name from YAML workflow.name field if present
        workflow_section = data.get("workflow")
        if isinstance(workflow_section, dict) and workflow_section.get("name"):
            entity_data["name"] = workflow_section["name"]

        return WorkflowEntity(**entity_data)

    def _assert_valid_yaml_for_write(self, workflow_id: str, raw_yaml: str) -> None:
        try:
            data = yaml_mod.safe_load(raw_yaml)
        except yaml_mod.YAMLError as exc:
            raise InputValidationError("Malformed YAML") from exc
        if not isinstance(data, dict):
            raise InputValidationError("YAML content is not a mapping")
        embedded_id = data.get("id")
        if not isinstance(embedded_id, str) or not embedded_id:
            raise InputValidationError("Workflow must have an id")
        kind = data.get("kind")
        if kind != "workflow":
            raise InputValidationError("kind must be 'workflow'")
        try:
            validate_entity_id(embedded_id, EntityKind.WORKFLOW)
        except ValueError as exc:
            raise InputValidationError(str(exc)) from exc
        if embedded_id != workflow_id:
            raise InputValidationError(
                f"embedded workflow id {embedded_id!r} does not match requested "
                f"{_workflow_ref(workflow_id)}"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def patch_yaml_field(self, workflow_id: str, field: str, value: Any) -> WorkflowEntity:
        """Update a single top-level field in a workflow YAML file.

        Uses ruamel.yaml to preserve comments and formatting.
        Writes atomically via _atomic_write.

        Raises:
            WorkflowNotFound: If the workflow file does not exist.
            InputValidationError: If the YAML content is malformed.
        """
        yaml_path = self._get_path(workflow_id)
        if not yaml_path.exists():
            raise WorkflowNotFound(f"Workflow {_workflow_ref(workflow_id)} not found")

        raw_yaml = yaml_path.read_text()

        ryaml = YAML()
        ryaml.preserve_quotes = True
        try:
            data = ryaml.load(raw_yaml)
        except Exception as e:
            raise InputValidationError(f"Malformed YAML: {e}") from e

        if not isinstance(data, dict):
            raise InputValidationError("YAML content is not a mapping")

        data[field] = value

        stream = io.StringIO()
        ryaml.dump(data, stream)
        updated_yaml = stream.getvalue()

        self._assert_valid_yaml_for_write(workflow_id, updated_yaml)
        self._atomic_write(yaml_path, updated_yaml)

        # Re-read and build entity from the written file
        parsed = yaml_mod.safe_load(updated_yaml) or {}
        canvas_state = self._read_canvas_sidecar(workflow_id)
        return self._build_entity(parsed, workflow_id, canvas_state, raw_yaml=updated_yaml)

    def list_all(self) -> List[WorkflowEntity]:
        """List all workflows found in custom/workflows/*.yaml."""
        workflows: List[WorkflowEntity] = []
        for file in sorted(self.workflows_dir.glob("*.yaml")):
            try:
                raw_yaml = file.read_text()
                data = yaml_mod.safe_load(raw_yaml) or {}
                canvas_state = self._read_canvas_sidecar(file.stem)
                workflows.append(self._build_entity(data, file.stem, canvas_state, raw_yaml))
            except Exception as e:
                logger.warning("Failed to parse workflow file %s: %s", file, e)
        return workflows

    def get_by_id(self, workflow_id: str) -> Optional[WorkflowEntity]:
        """Retrieve a workflow by its embedded id."""
        yaml_path = self._get_path(workflow_id)
        if not yaml_path.exists():
            return None

        try:
            raw_yaml = yaml_path.read_text()
            data = yaml_mod.safe_load(raw_yaml) or {}
        except Exception as e:
            logger.warning("Failed to parse workflow file %s: %s", yaml_path, e)
            return None

        canvas_state = self._read_canvas_sidecar(workflow_id)
        return self._build_entity(data, workflow_id, canvas_state, raw_yaml)

    def get_file_mtime(self, workflow_id: str) -> float | None:
        yaml_path = self._get_path(workflow_id)
        if not yaml_path.exists():
            return None
        return yaml_path.stat().st_mtime

    def get_block_count(self, workflow_id: str) -> int:
        yaml_path = self._get_path(workflow_id)
        if not yaml_path.exists():
            return 0

        try:
            raw_yaml = yaml_path.read_text()
            data = yaml_mod.safe_load(raw_yaml) or {}
        except Exception as e:
            logger.warning("Failed to read workflow blocks for %s: %s", workflow_id, e)
            return 0

        blocks = data.get("blocks", {})
        return len(blocks) if isinstance(blocks, dict) else 0

    def create(self, data: Dict[str, Any]) -> WorkflowEntity:
        """Create a new workflow file.

        The workflow id must be embedded in the YAML payload and drives the
        filename stem.
        """
        raw_yaml = data.get("yaml")
        if raw_yaml is None:
            raise InputValidationError("yaml is required")
        parsed_data = yaml_mod.safe_load(raw_yaml)
        if not isinstance(parsed_data, dict):
            raise InputValidationError("YAML content is not a mapping")
        stem = parsed_data.get("id")
        if not isinstance(stem, str) or not stem:
            raise InputValidationError("Workflow must have an id")
        yaml_path = self._get_path(stem)
        if yaml_path.exists():
            raise InputValidationError(f"Workflow {_workflow_ref(stem)} already exists")

        canvas_state = data.get("canvas_state")
        yaml_content = raw_yaml
        self._assert_valid_yaml_for_write(stem, yaml_content)
        entity = self._build_entity(
            parsed_data,
            stem,
            canvas_state if isinstance(canvas_state, dict) else None,
            raw_yaml=yaml_content,
        )

        # Atomic write YAML (D5: YAML first, then canvas)
        self._atomic_write(yaml_path, yaml_content)

        # Write canvas sidecar (failure is acceptable per D5)
        self._write_canvas_sidecar(stem, canvas_state)

        return entity

    def update(self, workflow_id: str, data: Dict[str, Any]) -> WorkflowEntity:
        """Update an existing workflow file.

        Writes the provided canonical raw YAML back atomically after validating
        the embedded workflow id.
        """
        yaml_path = self._get_path(workflow_id)
        if not yaml_path.exists():
            raise WorkflowNotFound(f"Workflow {_workflow_ref(workflow_id)} not found")

        # Do NOT mutate the input dict — use .get() instead of .pop()
        canvas_state_update = data.get("canvas_state")
        raw_yaml = data.get("yaml")
        if raw_yaml is None:
            raise InputValidationError("yaml is required")
        yaml_content = raw_yaml
        next_name = data.get("name")

        if next_name is not None:
            ryaml = YAML()
            ryaml.preserve_quotes = True
            try:
                yaml_doc = ryaml.load(yaml_content) if yaml_content.strip() else {}
            except Exception as e:
                raise InputValidationError(f"Malformed YAML: {e}") from e

            if yaml_doc is None:
                yaml_doc = {}

            if not isinstance(yaml_doc, dict):
                raise InputValidationError("YAML content is not a mapping")

            workflow_section = yaml_doc.get("workflow")
            if workflow_section is None:
                workflow_section = {}
                yaml_doc["workflow"] = workflow_section
            elif not isinstance(workflow_section, dict):
                raise InputValidationError("workflow section is not a mapping")

            workflow_section["name"] = next_name

            stream = io.StringIO()
            ryaml.dump(yaml_doc, stream)
            yaml_content = stream.getvalue()

        parsed_data = yaml_mod.safe_load(yaml_content) or {}
        if not isinstance(parsed_data, dict):
            raise InputValidationError("YAML content is not a mapping")
        embedded_id = parsed_data.get("id")
        if embedded_id != workflow_id:
            raise ValueError(
                f"embedded workflow id {embedded_id!r} does not match requested "
                f"{_workflow_ref(workflow_id)}"
            )
        self._assert_valid_yaml_for_write(workflow_id, yaml_content)
        self._build_entity(
            parsed_data,
            workflow_id,
            self._read_canvas_sidecar(workflow_id),
            raw_yaml=yaml_content,
        )
        self._atomic_write(yaml_path, yaml_content)

        # Update canvas sidecar if provided
        if canvas_state_update is not None:
            self._write_canvas_sidecar(workflow_id, canvas_state_update)

        # Parse written content for entity construction
        canvas_state = self._read_canvas_sidecar(workflow_id)
        return self._build_entity(parsed_data, workflow_id, canvas_state, raw_yaml=yaml_content)

    def delete(self, workflow_id: str) -> bool:
        """Delete a workflow and its canvas sidecar."""
        yaml_path = self._get_path(workflow_id)
        canvas_path = self._canvas_path(workflow_id)

        deleted = False
        if yaml_path.exists():
            yaml_path.unlink()
            deleted = True

        if canvas_path.exists():
            try:
                canvas_path.unlink()
            except Exception as e:
                logger.warning("Failed to delete canvas sidecar %s: %s", canvas_path, e)

        return deleted
