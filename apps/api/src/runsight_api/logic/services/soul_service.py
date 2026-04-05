import uuid
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from ...data.filesystem.soul_repo import SoulRepository
from ...domain.errors import InputValidationError, SoulAlreadyExists, SoulInUse, SoulNotFound
from ...domain.value_objects import SoulEntity, WorkflowEntity

logger = logging.getLogger(__name__)


class SoulService:
    def __init__(
        self, soul_repo: SoulRepository, git_service=None, workflow_repo=None, provider_repo=None
    ):
        self.soul_repo = soul_repo
        self.git_service = git_service
        self.workflow_repo = workflow_repo
        self.provider_repo = provider_repo

    @staticmethod
    def _soul_file_path(id: str) -> str:
        return f"custom/souls/{id}.yaml"

    @staticmethod
    def _extract_workflow_soul_ids(workflow: WorkflowEntity) -> List[str]:
        if not workflow.yaml:
            return []
        try:
            data = yaml.safe_load(workflow.yaml) or {}
        except Exception:
            return []

        blocks_section = data.get("blocks", {}) or {}
        if not isinstance(blocks_section, dict):
            return []

        soul_ids: List[str] = []
        seen: set[str] = set()
        for value in blocks_section.values():
            if not isinstance(value, dict):
                continue

            soul_ref = value.get("soul_ref")
            if isinstance(soul_ref, str) and soul_ref not in seen:
                seen.add(soul_ref)
                soul_ids.append(soul_ref)

            exits = value.get("exits", []) or []
            if not isinstance(exits, list):
                continue
            for exit_def in exits:
                if not isinstance(exit_def, dict):
                    continue
                exit_soul_ref = exit_def.get("soul_ref")
                if isinstance(exit_soul_ref, str) and exit_soul_ref not in seen:
                    seen.add(exit_soul_ref)
                    soul_ids.append(exit_soul_ref)
        return soul_ids

    def _resolve_workflow_repo(self, workflow_repo=None):
        return workflow_repo or self.workflow_repo

    @staticmethod
    def _normalize_soul_payload(data: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(data)
        if normalized.get("max_tool_iterations") is None:
            normalized["max_tool_iterations"] = 5
        return normalized

    def _validate_provider_state(self, provider_id: str | None) -> None:
        if not provider_id or not self.provider_repo:
            return
        provider = self.provider_repo.get_by_id(provider_id)
        if provider and not getattr(provider, "is_active", True):
            raise InputValidationError(f"Provider {provider_id} is disabled")

    def list_souls(self, query: Optional[str] = None, workflow_repo=None) -> List[SoulEntity]:
        souls = self.soul_repo.list_all()
        if query:
            query = query.lower()
            souls = [
                s for s in souls if query in s.id.lower() or (s.role and query in s.role.lower())
            ]
        workflow_repo = self._resolve_workflow_repo(workflow_repo)
        enriched_souls = [
            soul.model_copy(update={"modified_at": self.soul_repo.get_file_mtime(soul.id)})
            for soul in souls
        ]
        if workflow_repo:
            counts = self._compute_workflow_counts(enriched_souls, workflow_repo)
            enriched_souls = [
                soul.model_copy(update={"workflow_count": counts.get(soul.id, 0)})
                for soul in enriched_souls
            ]
        return enriched_souls

    def get_soul(self, id: str) -> Optional[SoulEntity]:
        soul = self.soul_repo.get_by_id(id)
        if soul is None:
            return None
        return soul.model_copy(update={"modified_at": self.soul_repo.get_file_mtime(soul.id)})

    def get_soul_usages(self, id: str, workflow_repo=None) -> List[Dict[str, Optional[str]]]:
        soul = self.get_soul(id)
        if not soul:
            raise SoulNotFound(f"Soul {id} not found")
        workflow_repo = self._resolve_workflow_repo(workflow_repo)
        return self._get_workflow_soul_refs(soul, workflow_repo)

    def _get_workflow_soul_refs(
        self, soul: SoulEntity, workflow_repo
    ) -> List[Dict[str, Optional[str]]]:
        usages: List[Dict[str, Optional[str]]] = []
        if not workflow_repo:
            return usages
        aliases = self._soul_reference_aliases(soul)
        for workflow in workflow_repo.list_all():
            workflow_soul_ids = self._extract_workflow_soul_ids(workflow)
            if any(soul_id in aliases for soul_id in workflow_soul_ids):
                usages.append({"workflow_id": workflow.id, "workflow_name": workflow.name})
        return usages

    def _compute_workflow_counts(self, souls: List[SoulEntity], workflow_repo) -> Dict[str, int]:
        counts = {soul.id: 0 for soul in souls}
        if not counts:
            return counts
        if not workflow_repo:
            return counts

        aliases_to_soul_ids: Dict[str, set[str]] = {}
        for soul in souls:
            for alias in self._soul_reference_aliases(soul):
                aliases_to_soul_ids.setdefault(alias, set()).add(soul.id)

        for workflow in workflow_repo.list_all():
            for soul_id in self._extract_workflow_soul_ids(workflow):
                for matching_soul_id in aliases_to_soul_ids.get(soul_id, ()):
                    counts[matching_soul_id] += 1
        return counts

    def _soul_reference_aliases(self, soul: SoulEntity) -> set[str]:
        aliases = {soul.id}
        resolve_existing_path = getattr(self.soul_repo, "_resolve_existing_path", None)
        if not callable(resolve_existing_path):
            return aliases

        try:
            file_path = resolve_existing_path(soul.id)
        except Exception:
            return aliases

        if isinstance(file_path, Path) and file_path.suffix == ".yaml":
            aliases.add(file_path.stem)

        return aliases

    def create_soul(self, data: Dict[str, Any]) -> SoulEntity:
        data = self._normalize_soul_payload(data)
        self._validate_provider_state(data.get("provider"))
        if "id" not in data or not data["id"]:
            data["id"] = f"soul_{uuid.uuid4().hex[:8]}"
        if self.soul_repo.get_by_id(data["id"]):
            raise SoulAlreadyExists(f"Soul {data['id']} already exists")
        result = self.soul_repo.create(data)
        self._auto_commit(f"Create {result.id}.yaml", [self._soul_file_path(result.id)])
        return result

    def update_soul(self, id: str, data: Dict[str, Any], copy_on_edit: bool = False) -> SoulEntity:
        data = self._normalize_soul_payload(data)
        existing = self.soul_repo.get_by_id(id)
        if not existing:
            raise SoulNotFound(f"Soul {id} not found")

        if copy_on_edit:
            # Create a new soul with a new ID
            new_id = f"{id}_copy_{uuid.uuid4().hex[:4]}"
            data["id"] = new_id
            self._validate_provider_state(data.get("provider"))
            result = self.soul_repo.create(data)
            self._auto_commit(f"Create {result.id}.yaml", [self._soul_file_path(result.id)])
            return result

        merged = existing.model_dump(exclude={"workflow_count"})
        merged.update(data)
        self._validate_provider_state(merged.get("provider"))
        result = self.soul_repo.update(id, merged)
        self._auto_commit(f"Update {id}.yaml", [self._soul_file_path(id)])
        return result

    def delete_soul(self, id: str, force: bool = False, workflow_repo=None) -> bool:
        soul = self.get_soul(id)
        if not soul:
            raise SoulNotFound(f"Soul {id} not found")

        workflow_repo = self._resolve_workflow_repo(workflow_repo)
        if workflow_repo and not force:
            usages = self._get_workflow_soul_refs(soul, workflow_repo)
            if usages:
                raise SoulInUse(
                    f"Soul {id!r} is referenced by {len(usages)} workflow(s)",
                    details={"usages": usages},
                )

        success = self.soul_repo.delete(id)
        if not success:
            raise SoulNotFound(f"Soul {id} not found")
        self._auto_commit(f"Delete {id}.yaml", [self._soul_file_path(id)])
        return True

    def _auto_commit(self, message: str, files: list) -> None:
        if not self.git_service:
            return
        try:
            if self.git_service.is_clean():
                return  # nothing changed, skip empty commit
            current_branch = self.git_service.current_branch()
            if not isinstance(current_branch, str) or not current_branch:
                current_branch = "main"
            if current_branch != "main":
                logger.info(
                    "Skipping soul auto-commit outside main branch",
                    extra={"current_branch": current_branch, "files": files},
                )
                return
            self.git_service.commit_to_branch("main", files, message)
        except Exception:
            logger.warning(
                "Soul auto-commit failed; keeping filesystem changes without git commit",
                exc_info=True,
                extra={"files": files, "message": message},
            )
