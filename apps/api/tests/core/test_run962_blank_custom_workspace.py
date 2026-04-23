"""Red tests for RUN-962: scaffold empty custom directories only."""

import os
import shutil
import subprocess
from pathlib import Path

from runsight_api.core.config import Settings, ensure_project_dirs

REPO_ROOT = Path(__file__).resolve().parents[4]
README = REPO_ROOT / "README.md"
FIRST_TIME_SETUP_DOC = (
    REPO_ROOT / "apps/site/src/content/docs/docs/configuration/first-time-setup.mdx"
)
DOCKER_ENTRYPOINT = REPO_ROOT / "docker-entrypoint.sh"

SAMPLE_RELATIVE_PATHS = (
    Path("custom/workflows/research-review.yaml"),
    Path("custom/souls/researcher.yaml"),
    Path("custom/souls/reviewer.yaml"),
    Path("custom/souls/writer.yaml"),
    Path("custom/tools/slack_payload_builder.yaml"),
    Path("custom/tools/slack_webhook.yaml"),
)

_PACKAGE_STARTUP_SNIPPET = """
from pathlib import Path
from runsight_api.main import app_settings
from runsight_api.core.config import ensure_project_dirs

ensure_project_dirs(app_settings)
print(Path(app_settings.base_path).resolve())
""".strip()

_API_STARTUP_SNIPPET = """
from pathlib import Path
from fastapi.testclient import TestClient
from runsight_api.main import app, app_settings

with TestClient(app):
    pass

print(Path(app_settings.base_path).resolve())
""".strip()


def _uv_executable() -> str:
    executable = shutil.which("uv")
    assert executable, "uv must be available to exercise the published-package startup contract"
    return executable


def _run_package_startup(
    cwd: Path,
    *,
    snippet: str = _PACKAGE_STARTUP_SNIPPET,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        _uv_executable(),
        "run",
        "--project",
        str(REPO_ROOT),
        "--package",
        "runsight",
        "python",
        "-c",
        snippet,
    ]
    merged_env = {**os.environ}
    if env is None or "RUNSIGHT_BASE_PATH" not in env:
        merged_env.pop("RUNSIGHT_BASE_PATH", None)
    merged_env.update(dict(env or {}))
    return subprocess.run(
        command,
        cwd=cwd,
        env=merged_env,
        check=False,
        capture_output=True,
        text=True,
    )


def _run_docker_startup(
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
    mounted_workspace_root: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    entrypoint = DOCKER_ENTRYPOINT
    if mounted_workspace_root is not None:
        entrypoint = cwd / "docker-entrypoint.host-test.sh"
        entrypoint.write_text(
            DOCKER_ENTRYPOINT.read_text(encoding="utf-8").replace(
                "/workspace", str(mounted_workspace_root)
            ),
            encoding="utf-8",
        )

    command = [
        "sh",
        str(entrypoint),
        _uv_executable(),
        "run",
        "--project",
        str(REPO_ROOT),
        "--package",
        "runsight",
        "python",
        "-c",
        _PACKAGE_STARTUP_SNIPPET,
    ]
    merged_env = {**os.environ}
    if env is None or "RUNSIGHT_BASE_PATH" not in env:
        merged_env.pop("RUNSIGHT_BASE_PATH", None)
    merged_env.update(dict(env or {}))
    return subprocess.run(
        command,
        cwd=cwd,
        env=merged_env,
        check=False,
        capture_output=True,
        text=True,
    )


def _custom_yaml_paths(workspace_root: Path) -> list[Path]:
    return sorted(
        path.relative_to(workspace_root)
        for pattern in ("custom/**/*.yaml", "custom/**/*.yml")
        for path in workspace_root.glob(pattern)
    )


class TestBlankWorkspaceSourceStartup:
    def test_source_startup_creates_empty_custom_dirs_and_no_sample_yaml(self, tmp_path: Path):
        settings = Settings(base_path=str(tmp_path))

        ensure_project_dirs(settings)

        assert (tmp_path / ".runsight").is_dir()
        assert (tmp_path / "custom" / "workflows").is_dir()
        assert (tmp_path / "custom" / "souls").is_dir()
        assert (tmp_path / "custom" / "tools").is_dir()
        assert _custom_yaml_paths(tmp_path) == []


class TestBlankWorkspacePublishedPackageStartup:
    def test_package_startup_creates_only_empty_custom_dirs(self, tmp_path: Path):
        workspace_root = tmp_path / "uvx-workspace"
        workspace_root.mkdir()

        result = _run_package_startup(
            workspace_root,
            env={"RUNSIGHT_BASE_PATH": str(workspace_root)},
        )

        assert result.returncode == 0, result.stderr
        assert (workspace_root / ".runsight").is_dir()
        assert (workspace_root / "custom" / "workflows").is_dir()
        assert (workspace_root / "custom" / "souls").is_dir()
        assert (workspace_root / "custom" / "tools").is_dir()
        assert _custom_yaml_paths(workspace_root) == []

    def test_api_boot_does_not_eagerly_create_custom_providers(self, tmp_path: Path):
        workspace_root = tmp_path / "api-workspace"
        workspace_root.mkdir()

        result = _run_package_startup(
            workspace_root,
            snippet=_API_STARTUP_SNIPPET,
            env={"RUNSIGHT_BASE_PATH": str(workspace_root)},
        )

        assert result.returncode == 0, result.stderr
        assert (workspace_root / ".runsight").is_dir()
        assert (workspace_root / "custom" / "workflows").is_dir()
        assert (workspace_root / "custom" / "souls").is_dir()
        assert (workspace_root / "custom" / "tools").is_dir()
        assert not (workspace_root / "custom" / "providers").exists()


class TestBlankWorkspaceDockerStartup:
    def test_docker_startup_creates_only_empty_custom_dirs(self, tmp_path: Path):
        mounted_workspace_root = tmp_path / "docker-workspace"
        mounted_workspace_root.mkdir()

        result = _run_docker_startup(
            mounted_workspace_root,
            mounted_workspace_root=mounted_workspace_root,
        )

        assert result.returncode == 0, result.stderr
        assert (mounted_workspace_root / ".runsight").is_dir()
        assert (mounted_workspace_root / "custom" / "workflows").is_dir()
        assert (mounted_workspace_root / "custom" / "souls").is_dir()
        assert (mounted_workspace_root / "custom" / "tools").is_dir()
        assert _custom_yaml_paths(mounted_workspace_root) == []


class TestShippedWorkspaceContent:
    def test_repo_does_not_ship_sample_custom_yaml_assets(self):
        unexpected = [path for path in SAMPLE_RELATIVE_PATHS if (REPO_ROOT / path).exists()]

        assert unexpected == [], (
            "Runsight should no longer ship sample custom YAML content in the repo/runtime "
            f"workspace path, but found: {unexpected}"
        )


class TestDocsGuidance:
    def test_readme_describes_blank_workspace_onboarding(self):
        text = README.read_text(encoding="utf-8").lower()

        mentions_blank_workspace = any(
            phrase in text
            for phrase in (
                "empty custom",
                "blank workspace",
                "empty workspace",
                "starts with empty",
            )
        )
        mentions_first_workflow_onboarding = any(
            phrase in text
            for phrase in (
                "create your first workflow",
                "add your first workflow",
                "write your first workflow",
                "start by creating",
            )
        )
        mentions_no_sample_content = any(
            phrase in text
            for phrase in (
                "no sample workflows",
                "no sample souls",
                "no sample tools",
                "sample content is not shipped",
            )
        )

        assert (
            mentions_blank_workspace
            and mentions_first_workflow_onboarding
            and mentions_no_sample_content
        ), (
            "README must describe blank-workspace startup, tell users to create their first "
            "workflow, and clarify that sample custom YAML is not pre-shipped."
        )

    def test_first_time_setup_doc_describes_empty_custom_dirs_without_marker(self):
        text = FIRST_TIME_SETUP_DOC.read_text(encoding="utf-8").lower()

        mentions_all_empty_dirs = all(
            phrase in text for phrase in ("custom/workflows", "custom/souls", "custom/tools")
        )
        mentions_blank_onboarding = any(
            phrase in text
            for phrase in (
                "create your first workflow",
                "add your first workflow",
                "blank workspace",
                "empty workspace",
            )
        )
        mentions_marker_removal = ".runsight-project" not in text

        assert mentions_all_empty_dirs and mentions_blank_onboarding and mentions_marker_removal, (
            "First-time setup docs must describe empty custom/workflows, custom/souls, and "
            "custom/tools scaffolding, explain first-workflow onboarding, and stop referring "
            "to the removed .runsight-project marker."
        )


class TestExistingUserAssetsPreserved:
    def test_existing_custom_assets_remain_unchanged(self, tmp_path: Path):
        workflows_dir = tmp_path / "custom" / "workflows"
        souls_dir = tmp_path / "custom" / "souls"
        tools_dir = tmp_path / "custom" / "tools"
        workflows_dir.mkdir(parents=True)
        souls_dir.mkdir(parents=True)
        tools_dir.mkdir(parents=True)

        workflow = workflows_dir / "user-workflow.yaml"
        soul = souls_dir / "user-soul.yaml"
        tool = tools_dir / "user-tool.yaml"
        workflow.write_text("name: user-workflow\n", encoding="utf-8")
        soul.write_text("id: user-soul\n", encoding="utf-8")
        tool.write_text("id: user-tool\n", encoding="utf-8")

        settings = Settings(base_path=str(tmp_path))
        ensure_project_dirs(settings)

        assert workflow.read_text(encoding="utf-8") == "name: user-workflow\n"
        assert soul.read_text(encoding="utf-8") == "id: user-soul\n"
        assert tool.read_text(encoding="utf-8") == "id: user-tool\n"
        assert _custom_yaml_paths(tmp_path) == [
            Path("custom/souls/user-soul.yaml"),
            Path("custom/tools/user-tool.yaml"),
            Path("custom/workflows/user-workflow.yaml"),
        ]
