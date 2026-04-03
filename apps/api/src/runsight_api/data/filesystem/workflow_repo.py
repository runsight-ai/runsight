"""
Filesystem-backed workflow repository.

Writes valid RunsightWorkflowFile YAML to custom/workflows/ with atomic writes.
Canvas state is stored as a JSON sidecar in custom/workflows/.canvas/.

ADR D3: The id field is NOT stored inside the YAML file — it is inferred
from the filename stem (e.g., onboarding-flow-k8x3m.yaml → id = "onboarding-flow-k8x3m").
"""

import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote

import yaml as yaml_mod
from pydantic import ValidationError as PydanticValidationError
from runsight_core.yaml.parser import (
    _validate_declared_tool_definitions,
    _discovery_module,
    validate_tool_governance,
)
from runsight_core.yaml.schema import RunsightWorkflowFile

from ...domain.errors import InputValidationError, WorkflowNotFound
from ...domain.value_objects import WorkflowEntity
from ._utils import atomic_write as _shared_atomic_write

logger = logging.getLogger(__name__)

# Fields that are API-only metadata, not part of the YAML file content
_META_FIELDS = {"id", "canvas_state", "yaml"}

# Maximum retries when a generated filename collides with an existing file
_MAX_COLLISION_RETRIES = 3


class WorkflowRepository:
    """Persists workflows as YAML files in custom/workflows/.

    Filename convention: {slug}-{short_id}.yaml
    Canvas sidecar: .canvas/{slug}-{short_id}.canvas.json

    The workflow id is the filename stem (ADR D3) — no id is stored inside
    the YAML content.
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
    def _generate_short_id() -> str:
        """Generate a 5-character base36 ID from timestamp + random component."""
        ts = int(time.time() * 1000)
        rand = random.randint(0, 36**2 - 1)
        combined = (ts % (36**3)) * (36**2) + rand
        chars = "0123456789abcdefghijklmnopqrstuvwxyz"
        result = []
        for _ in range(5):
            result.append(chars[combined % 36])
            combined //= 36
        return "".join(reversed(result))

    @staticmethod
    def _slugify(name: str) -> str:
        """Convert a workflow name to a URL-safe slug.

        - Lowercase
        - Replace non-alphanumeric characters with hyphens
        - Collapse consecutive hyphens
        - Strip leading/trailing hyphens
        - Truncate to 64 characters (ADR max length)
        """
        if not name:
            return "untitled"
        slug = name.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = re.sub(r"-{2,}", "-", slug)
        slug = slug.strip("-")
        if not slug:
            return "untitled"
        return slug[:64]

    @staticmethod
    def _build_filename(name: str, short_id: str) -> str:
        """Build the filename stem from a workflow name and short ID."""
        slug = WorkflowRepository._slugify(name)
        return f"{slug}-{short_id}"

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        """Write content to a file atomically via temp file + rename.

        Delegates to the shared utility in _utils.py.
        """
        _shared_atomic_write(path, content)

    def _get_path(self, workflow_id: str) -> Path:
        """Get the YAML file path for a workflow id (= filename stem)."""
        decoded = unquote(workflow_id)
        if ".." in decoded or "/" in decoded or "\\" in decoded:
            raise ValueError(f"Invalid path traversal in id: {workflow_id!r}")
        result = self.workflows_dir / f"{workflow_id}.yaml"
        if not str(result.resolve()).startswith(str(self.workflows_dir.resolve())):
            raise ValueError("Path traversal detected: resolved path escapes base directory")
        return result

    def _canvas_path(self, stem: str) -> Path:
        return self.canvas_dir / f"{stem}.canvas.json"

    def _validate_yaml_content(self, raw_yaml: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Validate raw YAML string against RunsightWorkflowFile schema.

        Returns (valid, validation_error) — never raises.
        If raw_yaml is None or empty, returns (False, ...).
        """
        if not raw_yaml:
            return False, "No YAML content to validate"
        try:
            data = yaml_mod.safe_load(raw_yaml)
            if not isinstance(data, dict):
                return False, "YAML content is not a mapping"
            file_def = RunsightWorkflowFile.model_validate(data)
            souls_dir = Path(self.base_path) / "custom" / "souls"
            souls_map = _discovery_module._discover_souls(souls_dir)
            validate_tool_governance(file_def, souls_map)
            _validate_declared_tool_definitions(
                file_def,
                base_dir=str(self.base_path),
                require_custom_metadata=True,
            )
            return True, None
        except PydanticValidationError as e:
            return False, str(e)
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Unexpected validation error: {e}"

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
            data: Parsed YAML data dict (without id).
            stem: Filename stem — this IS the workflow id (ADR D3).
            canvas_state: Optional canvas sidecar data.
            raw_yaml: Raw YAML file content (WYSIWYG). If None, the yaml
                      field in the entity will be None.
        """
        # Validate the raw YAML content against RunsightWorkflowFile schema
        valid, validation_error = self._validate_yaml_content(raw_yaml)

        entity_data = dict(data)
        # id comes from the filename stem, not from inside the YAML
        entity_data["id"] = stem
        entity_data["yaml"] = raw_yaml
        entity_data["valid"] = valid
        entity_data["validation_error"] = validation_error
        entity_data["filename"] = f"{stem}.yaml"
        if canvas_state is not None:
            entity_data["canvas_state"] = canvas_state

        # Extract name from YAML workflow.name field
        workflow_section = data.get("workflow")
        if isinstance(workflow_section, dict) and workflow_section.get("name"):
            entity_data["name"] = workflow_section["name"]

        return WorkflowEntity(**entity_data)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_all(self) -> List[WorkflowEntity]:
        """List all workflows found in custom/workflows/*.yaml.

        Every .yaml file is included — the id is the filename stem (ADR D3).
        """
        workflows: List[WorkflowEntity] = []
        for file in sorted(self.workflows_dir.glob("*.yaml")):
            raw_yaml = ""
            try:
                raw_yaml = file.read_text()
                data = yaml_mod.safe_load(raw_yaml) or {}
            except Exception as e:
                logger.warning("Failed to parse workflow file %s: %s", file, e)
                data = {}
            canvas_state = self._read_canvas_sidecar(file.stem)
            workflows.append(self._build_entity(data, file.stem, canvas_state, raw_yaml))
        return workflows

    def get_by_id(self, workflow_id: str) -> Optional[WorkflowEntity]:
        """Retrieve a workflow by its id (= filename stem)."""
        yaml_path = self._get_path(workflow_id)
        if not yaml_path.exists():
            return None

        raw_yaml = ""
        try:
            raw_yaml = yaml_path.read_text()
            data = yaml_mod.safe_load(raw_yaml) or {}
        except Exception as e:
            logger.warning("Failed to parse workflow file %s: %s", yaml_path, e)
            data = {}

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

        The workflow id is the generated filename stem (slug-shortid).
        Always saves the file (permissive save). Returns the entity with
        valid/validation_error indicating schema conformance.
        """
        name = data.get("name") or "untitled"
        raw_yaml = data.get("yaml")
        if raw_yaml is None:
            raise InputValidationError("yaml is required")

        # Generate filename with collision retry (Fix 6)
        stem = None
        for _ in range(_MAX_COLLISION_RETRIES):
            short_id = self._generate_short_id()
            candidate = self._build_filename(name, short_id)
            if not self._get_path(candidate).exists():
                stem = candidate
                break
        if stem is None:
            # Last attempt — extremely unlikely to still collide
            short_id = self._generate_short_id()
            stem = self._build_filename(name, short_id)

        # Do NOT mutate the input dict — use .get() instead of .pop()
        canvas_state = data.get("canvas_state")
        yaml_content = raw_yaml

        # Atomic write YAML (D5: YAML first, then canvas)
        self._atomic_write(self._get_path(stem), yaml_content)

        # Write canvas sidecar (failure is acceptable per D5)
        self._write_canvas_sidecar(stem, canvas_state)

        # Parse the written YAML to build the entity data dict
        parsed_data = yaml_mod.safe_load(yaml_content) or {}
        return self._build_entity(
            parsed_data,
            stem,
            canvas_state if isinstance(canvas_state, dict) else None,
            raw_yaml=yaml_content,
        )

    def update(self, workflow_id: str, data: Dict[str, Any]) -> WorkflowEntity:
        """Update an existing workflow file.

        Writes the provided canonical raw YAML back atomically.
        """
        yaml_path = self._get_path(workflow_id)
        if not yaml_path.exists():
            raise WorkflowNotFound(f"Workflow {workflow_id} not found")

        # Do NOT mutate the input dict — use .get() instead of .pop()
        canvas_state_update = data.get("canvas_state")
        raw_yaml = data.get("yaml")
        if raw_yaml is None:
            raise InputValidationError("yaml is required")
        yaml_content = raw_yaml

        self._atomic_write(yaml_path, yaml_content)

        # Update canvas sidecar if provided
        if canvas_state_update is not None:
            self._write_canvas_sidecar(workflow_id, canvas_state_update)

        # Parse written content for entity construction
        parsed_data = yaml_mod.safe_load(yaml_content) or {}
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
