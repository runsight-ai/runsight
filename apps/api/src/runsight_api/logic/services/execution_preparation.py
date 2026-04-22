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


def _requires_git_snapshot(branch: str) -> bool:
    return branch != "main"


def _workflow_ref(workflow_id: str) -> str:
    return str(EntityRef(EntityKind.WORKFLOW, workflow_id))


def _provider_ref(provider_id: str) -> str:
    return str(EntityRef(EntityKind.PROVIDER, provider_id))


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
        branch: str,
        parser: Callable[..., Any],
        prepare_runtime_workflow: Callable[..., tuple[dict[str, Any], RunsightTeamRunner | None]],
        get_workflow_commit_sha: Callable[[str], Optional[str]],
    ) -> PreparedWorkflow:
        wf_entity = self.workflow_repo.get_by_id(workflow_id)
        workflow_path = str(self.workflow_repo._get_path(workflow_id))
        registry_git_ref = branch if self.git_service else None
        registry_git_service = self.git_service

        if self.git_service:
            try:
                yaml_content = self.git_service.read_file(workflow_path, branch)
                commit_sha = self.git_service.get_sha(branch, workflow_path)
            except Exception:
                raise
            if commit_sha is None:
                raise ValueError(
                    f"Requested snapshot sha could not be resolved for workflow "
                    f"{_workflow_ref(workflow_id)} on ref {branch!r}"
                )
        else:
            if _requires_git_snapshot(branch):
                raise ValueError(
                    f"Requested snapshot could not be loaded for workflow "
                    f"{_workflow_ref(workflow_id)} on ref {branch!r}: git service unavailable"
                )
            if wf_entity is None:
                raise ValueError(f"Workflow {_workflow_ref(workflow_id)} not found")
            yaml_content = wf_entity.yaml
            commit_sha = get_workflow_commit_sha(workflow_path)

        api_keys = self.resolve_api_keys()
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
                git_ref=registry_git_ref,
                git_service=registry_git_service,
            )

        workflow = parser(
            yaml_content,
            workflow_registry=workflow_registry,
            api_keys=api_keys,
            runner=runner,
            _base_dir=str(getattr(self.workflow_repo, "base_path", ".")),
        )
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
