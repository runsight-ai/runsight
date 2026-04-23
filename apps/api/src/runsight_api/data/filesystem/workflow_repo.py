"""
Filesystem-backed workflow repository.

Writes valid RunsightWorkflowFile YAML to custom/workflows/ with atomic writes.
Canvas state is stored as a JSON sidecar in custom/workflows/.canvas/.

The workflow id is embedded in the YAML file and is the canonical identity.
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

import yaml as yaml_mod
from ruamel.yaml import YAML
from runsight_core.identity import EntityKind, EntityRef
from runsight_core.yaml.discovery import SoulScanner, WorkflowScanner
from runsight_core.yaml.parser import _validate_declared_tool_definitions, validate_tool_governance
from runsight_core.yaml.parser import validate_workflow_call_contracts
from runsight_core.yaml.schema import RunsightWorkflowFile

from ...domain.errors import InputValidationError, WorkflowNotFound
from ...domain.value_objects import WorkflowEntity
from ._utils import atomic_write as _shared_atomic_write
from .workflow_canvas_sidecar import read_canvas_sidecar, write_canvas_sidecar
from .workflow_entity_builder import build_workflow_entity
from .workflow_registry_builder import build_runnable_workflow_registry as build_registry
from .workflow_yaml_validation import assert_valid_yaml_for_write, validate_yaml_content

logger = logging.getLogger(__name__)


def _workflow_ref(workflow_id: str) -> str:
    return str(EntityRef(EntityKind.WORKFLOW, workflow_id))


class WorkflowRepository:
    """Persists workflows as YAML files in custom/workflows/."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.workflows_dir = self.base_path / "custom" / "workflows"
        self.canvas_dir = self.workflows_dir / ".canvas"
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        self.canvas_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        _shared_atomic_write(path, content)

    @staticmethod
    def _atomic_write_bytes(path: Path, content: bytes) -> None:
        parent = path.parent
        fd, tmp_path = tempfile.mkstemp(dir=parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(content)
            os.rename(tmp_path, str(path))
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _get_path(self, workflow_id: str) -> Path:
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
    ):
        return build_registry(
            base_path=self.base_path,
            workflow_id=workflow_id,
            raw_yaml=raw_yaml,
            root_path=self._get_path(workflow_id),
            git_ref=git_ref,
            git_service=git_service,
            workflow_scanner_cls=WorkflowScanner,
            workflow_call_contracts_validator=validate_workflow_call_contracts,
        )

    def _validate_yaml_content(
        self, workflow_id: str, raw_yaml: Optional[str]
    ) -> tuple[bool, Optional[str], list[dict[str, Optional[str]]]]:
        return validate_yaml_content(
            base_path=self.base_path,
            workflow_id=workflow_id,
            raw_yaml=raw_yaml,
            registry_builder=self.build_runnable_workflow_registry,
            declared_tool_definitions_validator=_validate_declared_tool_definitions,
            tool_governance_validator=validate_tool_governance,
            has_workflow_blocks=self._has_workflow_blocks,
            soul_scanner_cls=SoulScanner,
        )

    def _read_canvas_sidecar(self, stem: str) -> Optional[dict[str, Any]]:
        return read_canvas_sidecar(self._canvas_path(stem))

    def _write_canvas_sidecar(self, stem: str, canvas_state: Any) -> list[dict[str, str]]:
        return write_canvas_sidecar(
            stem=stem,
            canvas_state=canvas_state,
            path=self._canvas_path(stem),
            atomic_write=self._atomic_write,
        )

    @staticmethod
    def _raise_sidecar_write_failure(
        warnings: list[dict[str, Optional[str]]],
        *,
        workflow_id: str,
    ) -> None:
        if not warnings:
            return
        message = next(
            (
                warning.get("message")
                for warning in warnings
                if isinstance(warning.get("message"), str) and warning.get("message")
            ),
            None,
        )
        raise InputValidationError(
            message or f"Failed to persist canvas sidecar for workflow {_workflow_ref(workflow_id)}"
        )

    def _restore_canvas_sidecar(self, stem: str, previous_content: Optional[bytes | str]) -> None:
        canvas_path = self._canvas_path(stem)
        if previous_content is None:
            if canvas_path.exists():
                canvas_path.unlink()
            return
        if isinstance(previous_content, bytes):
            self._atomic_write_bytes(canvas_path, previous_content)
            return
        self._atomic_write(canvas_path, previous_content)

    def _read_canvas_sidecar_bytes(self, stem: str) -> Optional[bytes]:
        path = self._canvas_path(stem)
        if not path.exists():
            return None
        return path.read_bytes()

    def _write_canvas_sidecar_or_raise(self, stem: str, canvas_state: Any) -> None:
        self._raise_sidecar_write_failure(
            self._write_canvas_sidecar(stem, canvas_state),
            workflow_id=stem,
        )

    def _build_entity(
        self,
        data: Dict[str, Any],
        stem: str,
        canvas_state: Optional[Dict[str, Any]] = None,
        raw_yaml: Optional[str] = None,
        extra_warnings: Optional[list[dict[str, Optional[str]]]] = None,
    ) -> WorkflowEntity:
        return build_workflow_entity(
            data=data,
            stem=stem,
            validate_yaml_content=self._validate_yaml_content,
            canvas_state=canvas_state,
            raw_yaml=raw_yaml,
            extra_warnings=extra_warnings,
        )

    def _assert_valid_yaml_for_write(self, workflow_id: str, raw_yaml: str) -> None:
        assert_valid_yaml_for_write(workflow_id, raw_yaml)

    def _assert_existing_embedded_id_matches_target(
        self, workflow_id: str, yaml_path: Path
    ) -> None:
        try:
            existing_data = yaml_mod.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        except Exception:
            return
        if not isinstance(existing_data, dict):
            return
        existing_id = existing_data.get("id")
        if isinstance(existing_id, str) and existing_id != workflow_id:
            raise InputValidationError(
                f"{workflow_id}.yaml: embedded id '{existing_id}' does not match filename stem "
                f"'{workflow_id}'"
            )

    def patch_yaml_field(self, workflow_id: str, field: str, value: Any) -> WorkflowEntity:
        yaml_path = self._get_path(workflow_id)
        if not yaml_path.exists():
            raise WorkflowNotFound(f"Workflow {_workflow_ref(workflow_id)} not found")
        self._assert_existing_embedded_id_matches_target(workflow_id, yaml_path)

        raw_yaml = yaml_path.read_text(encoding="utf-8")
        ryaml = YAML()
        ryaml.preserve_quotes = True
        try:
            data = ryaml.load(raw_yaml)
        except Exception as exc:
            raise InputValidationError(f"Malformed YAML: {exc}") from exc

        if not isinstance(data, dict):
            raise InputValidationError("YAML content is not a mapping")

        data[field] = value
        stream = io.StringIO()
        ryaml.dump(data, stream)
        updated_yaml = stream.getvalue()

        self._assert_valid_yaml_for_write(workflow_id, updated_yaml)
        self._atomic_write(yaml_path, updated_yaml)

        parsed = yaml_mod.safe_load(updated_yaml) or {}
        canvas_state = self._read_canvas_sidecar(workflow_id)
        return self._build_entity(parsed, workflow_id, canvas_state, raw_yaml=updated_yaml)

    def list_all(self) -> List[WorkflowEntity]:
        workflows: List[WorkflowEntity] = []
        for file in sorted(self.workflows_dir.glob("*.yaml")):
            try:
                raw_yaml = file.read_text(encoding="utf-8")
                data = yaml_mod.safe_load(raw_yaml) or {}
                canvas_state = self._read_canvas_sidecar(file.stem)
                workflows.append(self._build_entity(data, file.stem, canvas_state, raw_yaml))
            except Exception as exc:
                logger.warning("Failed to parse workflow file %s: %s", file, exc)
        return workflows

    def get_by_id(self, workflow_id: str) -> Optional[WorkflowEntity]:
        yaml_path = self._get_path(workflow_id)
        if not yaml_path.exists():
            return None

        try:
            raw_yaml = yaml_path.read_text(encoding="utf-8")
            data = yaml_mod.safe_load(raw_yaml) or {}
        except Exception as exc:
            logger.warning("Failed to parse workflow file %s: %s", yaml_path, exc)
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
            raw_yaml = yaml_path.read_text(encoding="utf-8")
            data = yaml_mod.safe_load(raw_yaml) or {}
        except Exception as exc:
            logger.warning("Failed to read workflow blocks for %s: %s", workflow_id, exc)
            return 0

        blocks = data.get("blocks", {})
        return len(blocks) if isinstance(blocks, dict) else 0

    def create(self, data: Dict[str, Any]) -> WorkflowEntity:
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

        self._assert_valid_yaml_for_write(stem, raw_yaml)
        self._atomic_write(yaml_path, raw_yaml)

        canvas_state_input = data.get("canvas_state")
        try:
            if canvas_state_input is not None:
                self._write_canvas_sidecar_or_raise(stem, canvas_state_input)
        except Exception:
            try:
                if yaml_path.exists():
                    yaml_path.unlink()
            except Exception:
                logger.warning("Failed to roll back workflow YAML after sidecar failure: %s", stem)
            raise

        return self._build_entity(
            parsed_data,
            stem,
            self._read_canvas_sidecar(stem),
            raw_yaml=raw_yaml,
        )

    def update(self, workflow_id: str, data: Dict[str, Any]) -> WorkflowEntity:
        yaml_path = self._get_path(workflow_id)
        if not yaml_path.exists():
            raise WorkflowNotFound(f"Workflow {_workflow_ref(workflow_id)} not found")
        self._assert_existing_embedded_id_matches_target(workflow_id, yaml_path)

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
            except Exception as exc:
                raise InputValidationError(f"Malformed YAML: {exc}") from exc

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

        self._assert_valid_yaml_for_write(workflow_id, yaml_content)
        parsed_data = yaml_mod.safe_load(yaml_content) or {}
        if not isinstance(parsed_data, dict):
            raise InputValidationError("YAML content is not a mapping")

        previous_yaml = yaml_path.read_text(encoding="utf-8")
        previous_canvas_content = None
        canvas_state_update = data.get("canvas_state")
        if canvas_state_update is not None:
            canvas_path = self._canvas_path(workflow_id)
            if canvas_path.exists():
                previous_canvas_content = canvas_path.read_bytes()
        self._atomic_write(yaml_path, yaml_content)

        try:
            if canvas_state_update is not None:
                self._write_canvas_sidecar_or_raise(workflow_id, canvas_state_update)
        except Exception:
            try:
                self._atomic_write(yaml_path, previous_yaml)
            except Exception:
                logger.warning(
                    "Failed to restore workflow YAML after sidecar failure: %s", workflow_id
                )
            try:
                self._restore_canvas_sidecar(workflow_id, previous_canvas_content)
            except Exception:
                logger.warning(
                    "Failed to restore workflow canvas sidecar after sidecar failure: %s",
                    workflow_id,
                )
            raise

        return self._build_entity(
            parsed_data,
            workflow_id,
            self._read_canvas_sidecar(workflow_id),
            raw_yaml=yaml_content,
        )

    def delete(self, workflow_id: str) -> bool:
        yaml_path = self._get_path(workflow_id)
        canvas_path = self._canvas_path(workflow_id)

        deleted = False
        if yaml_path.exists():
            yaml_path.unlink()
            deleted = True

        if canvas_path.exists():
            try:
                canvas_path.unlink()
            except Exception as exc:
                logger.warning("Failed to delete canvas sidecar %s: %s", canvas_path, exc)

        return deleted
