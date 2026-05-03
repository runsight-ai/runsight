"""Preparation collaborator for loading runnable workflow snapshots."""

import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from runsight_core.identity import EntityKind, EntityRef
from runsight_core.runner import FallbackRoute, RunsightTeamRunner
import yaml

logger = logging.getLogger(__name__)


def _requires_git_snapshot(branch: str | None) -> bool:
    return branch is not None


def _explicit_branch(branch: str | None) -> str | None:
    if branch is None:
        return None
    if branch == "":
        raise ValueError("Branch ref must not be empty")
    return branch


def _workflow_ref(workflow_id: str) -> str:
    return str(EntityRef(EntityKind.WORKFLOW, workflow_id))


def _provider_ref(provider_id: str) -> str:
    return str(EntityRef(EntityKind.PROVIDER, provider_id))


def _snapshot_failure_reason(error: Exception) -> str:
    if isinstance(error, subprocess.CalledProcessError):
        stderr = (error.stderr or "").strip()
        stdout = (error.stdout or "").strip()
        if stderr:
            return stderr
        if stdout:
            return stdout
    return str(error)


def has_workflow_blocks(workflow_definition: Dict[str, Any]) -> bool:
    blocks = workflow_definition.get("blocks", {})
    if not isinstance(blocks, dict):
        return False
    return any(
        isinstance(block_def, dict) and block_def.get("type") == "workflow"
        for block_def in blocks.values()
    )


def get_workflow_commit_sha(workflow_path: str) -> Optional[str]:
    """Return the latest git SHA that touched *workflow_path*."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", workflow_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        sha = result.stdout.strip()
        return sha if sha else None
    except Exception:
        return None


@dataclass
class PreparedWorkflow:
    workflow: Any
    commit_sha: Optional[str]


@dataclass(frozen=True)
class ResolvedWorkflowSnapshot:
    workflow_id: str
    yaml_content: str
    commit_sha: Optional[str]
    git_ref: Optional[str]


class ExecutionPreparationService:
    """Owns requested-snapshot loading and runnable workflow construction."""

    def __init__(
        self,
        workflow_repo,
        provider_repo,
        *,
        git_service=None,
        secrets=None,
        settings_repo=None,
        workflow_registry_builder=None,
    ):
        self.workflow_repo = workflow_repo
        self.provider_repo = provider_repo
        self.git_service = git_service
        self.secrets = secrets
        self.settings_repo = settings_repo
        self.workflow_registry_builder = workflow_registry_builder

    def prepare_for_launch(
        self,
        *,
        workflow_id: str,
        branch: str | None,
        parser: Callable[..., Any],
        prepare_runtime_workflow: Callable[..., tuple[dict[str, Any], RunsightTeamRunner | None]],
        get_workflow_commit_sha: Callable[[str], Optional[str]],
    ) -> PreparedWorkflow:
        wf_entity = self.workflow_repo.get_by_id(workflow_id)
        workflow_path = str(self.workflow_repo._get_path(workflow_id))
        explicit_branch = _explicit_branch(branch)
        registry_git_ref = explicit_branch if _requires_git_snapshot(explicit_branch) else None
        registry_git_service = self.git_service if _requires_git_snapshot(explicit_branch) else None

        if _requires_git_snapshot(explicit_branch):
            if self.git_service is None:
                raise ValueError(
                    f"Requested snapshot could not be loaded for workflow "
                    f"{_workflow_ref(workflow_id)} on ref {explicit_branch!r}: git service unavailable"
                )
            try:
                yaml_content = self.git_service.read_file(workflow_path, explicit_branch)
                commit_sha = self.git_service.get_sha(explicit_branch, workflow_path)
            except Exception as exc:
                raise ValueError(
                    f"Requested snapshot could not be loaded for workflow "
                    f"{_workflow_ref(workflow_id)} on ref {explicit_branch!r}: "
                    f"{_snapshot_failure_reason(exc)}"
                ) from exc
            if commit_sha is None:
                raise ValueError(
                    f"Requested snapshot could not be loaded for workflow "
                    f"{_workflow_ref(workflow_id)} on ref {explicit_branch!r}: "
                    "requested snapshot sha could not be resolved"
                )
        else:
            if wf_entity is None:
                raise ValueError(f"Workflow {_workflow_ref(workflow_id)} not found")
            yaml_content = wf_entity.yaml
            commit_sha = get_workflow_commit_sha(workflow_path)

        return self._prepare_yaml_for_launch(
            workflow_id=workflow_id,
            yaml_content=yaml_content,
            commit_sha=commit_sha,
            git_ref=registry_git_ref,
            git_service=registry_git_service,
            parser=parser,
            prepare_runtime_workflow=prepare_runtime_workflow,
            requested_ref=explicit_branch,
        )

    def prepare_resolved_snapshot_for_launch(
        self,
        *,
        snapshot: ResolvedWorkflowSnapshot,
        parser: Callable[..., Any],
        prepare_runtime_workflow: Callable[..., tuple[dict[str, Any], RunsightTeamRunner | None]],
    ) -> PreparedWorkflow:
        return self._prepare_yaml_for_launch(
            workflow_id=snapshot.workflow_id,
            yaml_content=snapshot.yaml_content,
            commit_sha=snapshot.commit_sha,
            git_ref=snapshot.git_ref,
            git_service=self.git_service if snapshot.git_ref is not None else None,
            parser=parser,
            prepare_runtime_workflow=prepare_runtime_workflow,
            requested_ref=snapshot.git_ref,
        )

    def _prepare_yaml_for_launch(
        self,
        *,
        workflow_id: str,
        yaml_content: str,
        commit_sha: Optional[str],
        git_ref: str | None,
        git_service: Any,
        parser: Callable[..., Any],
        prepare_runtime_workflow: Callable[..., tuple[dict[str, Any], RunsightTeamRunner | None]],
        requested_ref: str | None,
    ) -> PreparedWorkflow:
        api_keys = self.resolve_api_keys()
        try:
            workflow_definition, runner = prepare_runtime_workflow(
                yaml_content=yaml_content,
                api_keys=api_keys,
            )

            workflow_registry = None
            if has_workflow_blocks(workflow_definition):
                registry_builder = self.workflow_registry_builder
                if registry_builder is None:
                    registry_builder = self.workflow_repo.build_runnable_workflow_registry
                workflow_registry = registry_builder(
                    workflow_id,
                    yaml_content,
                    git_ref=git_ref,
                    git_service=git_service,
                )

            workflow = parser(
                yaml_content,
                workflow_registry=workflow_registry,
                api_keys=api_keys,
                runner=runner,
                _base_dir=str(getattr(self.workflow_repo, "base_path", ".")),
                _discovery_git_ref=git_ref,
                _discovery_git_service=git_service,
            )
        except Exception as exc:
            if requested_ref is not None:
                raise ValueError(
                    f"Requested snapshot could not be loaded for workflow "
                    f"{_workflow_ref(workflow_id)} on ref {requested_ref!r}: "
                    f"{_snapshot_failure_reason(exc)}"
                ) from exc
            raise
        return PreparedWorkflow(workflow=workflow, commit_sha=commit_sha)

    def resolve_api_keys(self) -> Dict[str, str]:
        """Resolve provider API keys, with env var fallback."""
        result: Dict[str, str] = {}
        configured_provider_types: set[str] = set()
        disabled_provider_types: set[str] = set()

        try:
            providers = self.provider_repo.list_all()
            for provider in providers:
                provider_type = getattr(provider, "type", None)
                if not provider_type:
                    continue
                configured_provider_types.add(provider_type)
                if not getattr(provider, "is_active", True):
                    disabled_provider_types.add(provider_type)
                    continue
                if provider.api_key and self.secrets:
                    resolved = self.secrets.resolve(provider.api_key)
                    if resolved:
                        result[provider_type] = resolved
        except (TypeError, AttributeError):
            pass

        env_var_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        for provider_type, env_var in env_var_map.items():
            if provider_type in disabled_provider_types:
                continue
            if provider_type in configured_provider_types and provider_type not in result:
                continue
            if provider_type not in result:
                val = os.environ.get(env_var)
                if val:
                    result[provider_type] = val

        return result

    def prepare_runtime_workflow(
        self,
        *,
        yaml_content: str,
        api_keys: Dict[str, str],
    ) -> tuple[dict[str, Any], RunsightTeamRunner | None]:
        raw = yaml.safe_load(yaml_content)
        if not isinstance(raw, dict):
            raise ValueError("Workflow YAML must parse to a mapping")

        try:
            providers = self.provider_repo.list_all()
        except (AttributeError, TypeError):
            providers = []
        if not isinstance(providers, list):
            providers = []
        provider_by_id = {
            provider.id: provider for provider in providers if getattr(provider, "is_active", True)
        }
        fallback_routes = self._fallback_routes_by_provider(provider_by_id=provider_by_id)
        souls_section = raw.get("souls")
        if not isinstance(souls_section, dict):
            souls_section = {}
            raw["souls"] = souls_section

        for soul_key, soul_data in souls_section.items():
            if not isinstance(soul_data, dict):
                continue

            provider_id = soul_data.get("provider")
            model_name = soul_data.get("model_name")

            if not isinstance(provider_id, str) or not provider_id.strip():
                raise ValueError(f"Soul '{soul_key}' must define an explicit provider")

            provider = provider_by_id.get(provider_id)
            if provider is None:
                raise ValueError(
                    f"Soul '{soul_key}' references disabled or missing provider "
                    f"{_provider_ref(provider_id)}"
                )

            if not isinstance(model_name, str) or not model_name.strip():
                raise ValueError(f"Soul '{soul_key}' must define an explicit model_name")

            if model_name not in self._provider_models(provider):
                raise ValueError(
                    f"Soul '{soul_key}' model '{model_name}' does not belong to provider "
                    f"{_provider_ref(provider_id)}"
                )

        runner_model_name = next(
            (
                soul_data.get("model_name")
                for soul_data in souls_section.values()
                if isinstance(soul_data, dict)
                and isinstance(soul_data.get("model_name"), str)
                and soul_data.get("model_name").strip()
            ),
            None,
        )
        if runner_model_name is None:
            if souls_section:
                raise ValueError(
                    "Workflow must include at least one soul with explicit provider and model_name"
                )
            return raw, None

        runner = RunsightTeamRunner(
            model_name=runner_model_name,
            api_keys=api_keys,
            fallback_routes=fallback_routes,
        )
        return raw, runner

    def _fallback_routes_by_provider(
        self, *, provider_by_id: dict[str, Any]
    ) -> dict[str, FallbackRoute]:
        if self.settings_repo is None:
            return {}
        try:
            settings_config = self.settings_repo.get_settings()
        except (AttributeError, TypeError):
            return {}
        if not getattr(settings_config, "fallback_enabled", False):
            return {}

        routes: dict[str, FallbackRoute] = {}
        try:
            fallback_map = self.settings_repo.get_fallback_map()
        except (AttributeError, TypeError):
            fallback_map = []
        if not isinstance(fallback_map, list):
            return {}

        for entry in fallback_map:
            if entry.provider_id not in provider_by_id:
                continue
            target_provider = provider_by_id.get(entry.fallback_provider_id)
            if target_provider is None:
                continue
            if entry.fallback_model_id not in self._provider_models(target_provider):
                continue
            routes[entry.provider_id] = FallbackRoute(
                source_provider_id=entry.provider_id,
                target_provider_id=entry.fallback_provider_id,
                target_model_name=entry.fallback_model_id,
            )
        return routes

    @staticmethod
    def _provider_models(provider: Any) -> list[str]:
        models = getattr(provider, "models", None)
        if isinstance(models, list):
            return [str(model) for model in models]
        return []
