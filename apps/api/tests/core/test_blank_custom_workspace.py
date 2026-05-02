"""Blank workspace startup smoke coverage."""

from pathlib import Path

from runsight_api.core.config import Settings, ensure_project_dirs


def _custom_yaml_paths(workspace_root: Path) -> list[Path]:
    return sorted(
        path.relative_to(workspace_root)
        for pattern in ("custom/**/*.yaml", "custom/**/*.yml")
        for path in (workspace_root.glob(pattern))
    )


def test_startup_creates_empty_custom_workspace_skeleton(tmp_path: Path) -> None:
    settings = Settings(base_path=str(tmp_path))

    ensure_project_dirs(settings)

    assert Path(settings.base_path) == tmp_path.resolve()
    assert (tmp_path / ".runsight").is_dir()
    assert (tmp_path / "custom" / "workflows").is_dir()
    assert (tmp_path / "custom" / "workflows" / ".canvas").is_dir()
    assert (tmp_path / "custom" / "souls").is_dir()
    assert (tmp_path / "custom" / "tools").is_dir()
    assert _custom_yaml_paths(tmp_path) == []


def test_startup_preserves_existing_custom_assets(tmp_path: Path) -> None:
    user_workflow = tmp_path / "custom" / "workflows" / "user-workflow.yaml"
    user_workflow.parent.mkdir(parents=True)
    user_workflow.write_text("id: user-workflow\nkind: workflow\n", encoding="utf-8")

    ensure_project_dirs(Settings(base_path=str(tmp_path)))

    assert user_workflow.read_text(encoding="utf-8") == "id: user-workflow\nkind: workflow\n"
    assert _custom_yaml_paths(tmp_path) == [Path("custom/workflows/user-workflow.yaml")]
