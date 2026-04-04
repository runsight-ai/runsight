"""
Filesystem-backed workflow repository.

Writes valid RunsightWorkflowFile YAML to custom/workflows/ with atomic writes.
Canvas state is stored as a JSON sidecar in custom/workflows/.canvas/.

ADR D3: The id field is NOT stored inside the YAML file — it is inferred
from the filename stem (e.g., onboarding-flow-k8x3m.yaml → id = "onboarding-flow-k8x3m").
"""

import io
import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote

import yaml as yaml_mod
from ruamel.yaml import YAML
from pydantic import ValidationError as PydanticValidationError
from runsight_core.yaml.parser import (
    _validate_declared_tool_definitions,
    _discovery_module,
    validate_workflow_call_contracts,
    validate_tool_governance,
)
from runsight_core.yaml.registry import WorkflowRegistry
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

    @staticmethod
    def _has_workflow_blocks(file_def: RunsightWorkflowFile) -> bool:
        return any(block_def.type == "workflow" for block_def in file_def.blocks.values())

    def _candidate_workflow_paths(self, workflow_ref: str) -> List[Path]:
        root = self.base_path.resolve()
        ref_path = Path(workflow_ref)
        if ref_path.is_absolute():
            return [ref_path.resolve()]

        candidate_paths: List[Path] = []
        if workflow_ref.startswith("custom/"):
            candidate_paths.append((root / ref_path).resolve())
        else:
            candidate_paths.append((root / "custom" / "workflows" / ref_path).resolve())
            if ref_path.suffix == "":
                candidate_paths.append(
                    (root / "custom" / "workflows" / f"{workflow_ref}.yaml").resolve()
                )
                candidate_paths.append(
                    (root / "custom" / "workflows" / f"{workflow_ref}.yml").resolve()
                )
        return candidate_paths

    def _read_workflow_from_source(
        self,
        workflow_ref: str,
        *,
        git_ref: Optional[str] = None,
        git_service: Any = None,
        name_index: Optional[Dict[str, Tuple[Path, RunsightWorkflowFile]]] = None,
    ) -> Optional[Tuple[Path, RunsightWorkflowFile]]:
        if name_index is not None:
            indexed = name_index.get(workflow_ref)
            if indexed is not None:
                return indexed

        for candidate_path in self._candidate_workflow_paths(workflow_ref):
            try:
                if git_service is not None and git_ref is not None:
                    raw_yaml = git_service.read_file(str(candidate_path), git_ref)
                else:
                    if not candidate_path.exists():
                        continue
                    raw_yaml = candidate_path.read_text(encoding="utf-8")
            except Exception:
                continue

            data = yaml_mod.safe_load(raw_yaml)
            if not isinstance(data, dict):
                raise ValueError(f"Workflow '{workflow_ref}' YAML content is not a mapping")
            return candidate_path, RunsightWorkflowFile.model_validate(data)

        return None

    def _register_workflow_aliases(
        self,
        registry: WorkflowRegistry,
        validation_index: Dict[str, Tuple[Path, RunsightWorkflowFile]],
        workflow_path: Path,
        workflow_file: RunsightWorkflowFile,
    ) -> None:
        resolved_path = workflow_path.resolve()
        aliases = {str(resolved_path), workflow_path.stem}
        try:
            aliases.add(str(resolved_path.relative_to(self.base_path.resolve())))
        except ValueError:
            pass

        workflow_name = getattr(workflow_file.workflow, "name", None)
        if workflow_name:
            aliases.add(workflow_name)

        for alias in aliases:
            registry.register(alias, workflow_file)
            validation_index[alias] = (resolved_path, workflow_file)

    def _build_name_index(
        self,
        *,
        git_ref: Optional[str] = None,
        git_service: Any = None,
    ) -> Dict[str, Tuple[Path, RunsightWorkflowFile]]:
        """Pre-scan all workflow files and build an alias-to-file index.

        Indexes by resolved path, filename stem, relative path, and
        workflow.name so that child refs can be resolved by any alias.
        Uses git_service to read from a branch snapshot when available,
        otherwise reads from the filesystem.
        """
        index: Dict[str, Tuple[Path, RunsightWorkflowFile]] = {}
        root = self.base_path.resolve()

        if git_service is not None and git_ref is not None:
            import subprocess

            result = subprocess.run(
                ["git", "ls-tree", "-r", "--name-only", git_ref, "--", "custom/workflows/"],
                cwd=str(git_service.repo_path),
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    line = line.strip()
                    if not line or not (line.endswith(".yaml") or line.endswith(".yml")):
                        continue
                    try:
                        raw_yaml = git_service.read_file(line, git_ref)
                        data = yaml_mod.safe_load(raw_yaml)
                        if not isinstance(data, dict):
                            continue
                        wf_file = RunsightWorkflowFile.model_validate(data)
                    except Exception:
                        continue
                    wf_path = (root / line).resolve()
                    aliases = {str(wf_path), Path(line).stem, line}
                    wf_name = getattr(wf_file.workflow, "name", None)
                    if wf_name:
                        aliases.add(wf_name)
                    for alias in aliases:
                        index[alias] = (wf_path, wf_file)
        else:
            for pattern in ("*.yaml", "*.yml"):
                for wf_path in self.workflows_dir.glob(pattern):
                    try:
                        raw_yaml = wf_path.read_text(encoding="utf-8")
                        data = yaml_mod.safe_load(raw_yaml)
                        if not isinstance(data, dict):
                            continue
                        wf_file = RunsightWorkflowFile.model_validate(data)
                    except Exception:
                        continue
                    resolved = wf_path.resolve()
                    aliases = {str(resolved), wf_path.stem}
                    try:
                        aliases.add(str(resolved.relative_to(root)))
                    except ValueError:
                        pass
                    wf_name = getattr(wf_file.workflow, "name", None)
                    if wf_name:
                        aliases.add(wf_name)
                    for alias in aliases:
                        index[alias] = (resolved, wf_file)

        return index

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
        root_path = self._get_path(workflow_id).resolve()
        registry = WorkflowRegistry(allow_filesystem_fallback=False)
        validation_index: Dict[str, Tuple[Path, RunsightWorkflowFile]] = {}
        self._register_workflow_aliases(registry, validation_index, root_path, root_file)

        name_index = self._build_name_index(git_ref=git_ref, git_service=git_service)

        pending: List[RunsightWorkflowFile] = [root_file]
        loaded_paths = {str(root_path)}

        while pending:
            current_file = pending.pop()
            for block_def in current_file.blocks.values():
                if block_def.type != "workflow":
                    continue

                resolved_child = self._read_workflow_from_source(
                    block_def.workflow_ref,
                    git_ref=git_ref,
                    git_service=git_service,
                    name_index=name_index,
                )
                if resolved_child is None:
                    continue

                child_path, child_file = resolved_child
                child_ref = str(child_path.resolve())
                if child_ref in loaded_paths:
                    continue

                loaded_paths.add(child_ref)
                self._register_workflow_aliases(registry, validation_index, child_path, child_file)
                pending.append(child_file)

        validate_workflow_call_contracts(
            root_file,
            base_dir=str(self.base_path),
            validation_index=validation_index,
            current_workflow_ref=str(root_path),
            allow_filesystem_fallback=False,
        )
        return registry

    def _validate_yaml_content(
        self, workflow_id: str, raw_yaml: Optional[str]
    ) -> Tuple[bool, Optional[str]]:
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
            if self._has_workflow_blocks(file_def):
                self.build_runnable_workflow_registry(workflow_id, raw_yaml)
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
        valid, validation_error = self._validate_yaml_content(stem, raw_yaml)

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
            raise WorkflowNotFound(f"Workflow {workflow_id} not found")

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

        self._atomic_write(yaml_path, updated_yaml)

        # Re-read and build entity from the written file
        parsed = yaml_mod.safe_load(updated_yaml) or {}
        canvas_state = self._read_canvas_sidecar(workflow_id)
        return self._build_entity(parsed, workflow_id, canvas_state, raw_yaml=updated_yaml)

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
