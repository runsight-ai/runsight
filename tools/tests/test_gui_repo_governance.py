"""
Governance tests for GUI repo-layout, source, and package-boundary rules.

Owner: tools/tests owns repo-wide static governance that scans GUI source,
packages/ui package metadata, and the GUI E2E harness layout.
Boundary: GUI Vitest suites own behavior. This suite preserves durable static
rules only: workspace ownership, imports, explicit package exports, retired
token usage, and E2E fixture ownership.
Exit criteria: delete or narrow this suite once these checks are enforced by
lint rules, ownership manifests, or generated package/build metadata.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GUI_ROOT = REPO_ROOT / "apps" / "gui"
GUI_SRC = GUI_ROOT / "src"
UI_PACKAGE_JSON = REPO_ROOT / "packages" / "ui" / "package.json"
E2E_TESTS = REPO_ROOT / "testing" / "gui-e2e" / "tests"
E2E_READONLY_SPEC = E2E_TESTS / "readonly-surface.spec.ts"

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class RetiredToken:
    name: str
    kind: str
    pattern: re.Pattern[str]
    safe_samples: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceFile:
    relative_path: str
    path: Path
    source: str


def _retired_token(
    name: str,
    kind: str,
    pattern: str | None = None,
    safe_samples: tuple[str, ...] = (),
) -> RetiredToken:
    return RetiredToken(name, kind, re.compile(pattern or re.escape(name)), safe_samples)


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _line_hits(path: Path, patterns: Iterable[re.Pattern[str]]) -> list[str]:
    source = _read(path)

    return [
        f"{_relative(path)}:{line_number}: {line.strip()}"
        for line_number, line in enumerate(source.splitlines(), start=1)
        if any(pattern.search(line) for pattern in patterns)
    ]


def _walk_files(root: Path) -> list[Path]:
    if not root.exists():
        return []

    return sorted(path for path in root.rglob("*") if path.is_file())


def _is_runtime_ts_source(path: Path) -> bool:
    if path.suffix not in {".ts", ".tsx"}:
        return False
    if "__tests__" in path.parts:
        return False
    if re.search(r"\.(?:test|stories)\.tsx?$", path.name):
        return False
    return True


def _runtime_gui_sources(root: Path = GUI_SRC) -> list[Path]:
    return [path for path in _walk_files(root) if _is_runtime_ts_source(path)]


PHANTOM_WORKFLOW_FIELDS = (
    "status",
    "updated_at",
    "created_at",
    "last_run_duration",
    "last_run_cost_usd",
    "last_run_completed_at",
    "step_count",
)

WORKFLOW_RESPONSE_SOURCES = (
    GUI_SRC / "features" / "flows" / "WorkflowRow.tsx",
    GUI_SRC / "features" / "flows" / "WorkflowsTab.tsx",
)

TOKEN_SWEEP_FILES = (
    "components/shared/DataTable.tsx",
    "components/shared/DeleteConfirmDialog.tsx",
    "components/shared/ErrorBoundary.tsx",
    "components/shared/PageHeader.tsx",
    "components/shared/StatusBadge.tsx",
    "components/provider/ProviderSetup.tsx",
    "features/surface/SurfaceCanvas.tsx",
    "features/surface/nodes/SoulNode.tsx",
    "features/surface/nodes/StartNode.tsx",
    "features/surface/SurfaceInspectorPanel.tsx",
    "features/surface/WorkflowSurface.tsx",
    "features/surface/surfaceUtils.ts",
    "features/settings/ModelsTab.tsx",
    "features/settings/ProvidersTab.tsx",
    "features/settings/SettingsPage.tsx",
    "features/dashboard/DashboardOrOnboarding.tsx",
    "routes/layouts/ShellLayout.tsx",
    "utils/icons.tsx",
)

RETIRED_TOKENS = (
    _retired_token("bg-background", "tailwind", r"\bbg-background\b"),
    _retired_token("bg-card", "tailwind", r"\bbg-card\b"),
    _retired_token("bg-popover", "tailwind", r"\bbg-popover\b"),
    _retired_token(
        "bg-primary",
        "tailwind",
        r"\bbg-primary(?!-foreground\b)(?![\w-])",
        ("bg-primary-foreground",),
    ),
    _retired_token(
        "bg-secondary",
        "tailwind",
        r"\bbg-secondary(?!-foreground\b)(?![\w-])",
        ("bg-secondary-foreground",),
    ),
    _retired_token(
        "bg-muted", "tailwind", r"\bbg-muted(?!-foreground\b)(?![\w-])", ("bg-muted-foreground",)
    ),
    _retired_token(
        "bg-accent", "tailwind", r"\bbg-accent(?!-foreground\b)(?![\w-])", ("bg-accent-foreground",)
    ),
    _retired_token("bg-destructive", "tailwind", r"\bbg-destructive(?![\w-])"),
    _retired_token("text-foreground", "tailwind", r"\btext-foreground(?![\w-])"),
    _retired_token("text-primary-foreground", "tailwind", r"\btext-primary-foreground\b"),
    _retired_token("text-muted-foreground", "tailwind", r"\btext-muted-foreground\b"),
    _retired_token("text-card-foreground", "tailwind", r"\btext-card-foreground\b"),
    _retired_token("text-popover-foreground", "tailwind", r"\btext-popover-foreground\b"),
    _retired_token("text-secondary-foreground", "tailwind", r"\btext-secondary-foreground\b"),
    _retired_token("text-accent-foreground", "tailwind", r"\btext-accent-foreground\b"),
    _retired_token("text-destructive", "tailwind", r"\btext-destructive(?![\w-])"),
    _retired_token(
        "border-border",
        "tailwind",
        r"\bborder-border"
        r"(?!-default\b)(?!-focus\b)(?!-hover\b)(?!-accent\b)(?!-danger\b)"
        r"(?!-success\b)(?!-warning\b)(?!-info\b)(?!-subtle\b)(?![\w-])",
        (
            "border-border-default",
            "border-border-focus",
            "border-border-hover",
            "border-border-accent",
            "border-border-danger",
            "border-border-success",
            "border-border-warning",
            "border-border-info",
            "border-border-subtle",
        ),
    ),
    _retired_token("border-input", "tailwind", r"\bborder-input(?![\w-])"),
    _retired_token("ring-ring", "tailwind", r"\bring-ring(?![\w-])"),
    _retired_token("var(--background)", "var", r"var\(--background\)"),
    _retired_token("var(--foreground)", "var", r"var\(--foreground\)"),
    _retired_token(
        "var(--primary)", "var", r"var\(--primary\)", ("var(--primary-hover)", "var(--primary-12)")
    ),
    _retired_token("var(--border)", "var", r"var\(--border\)", ("var(--border-default)",)),
    _retired_token("var(--card)", "var", r"var\(--card\)"),
    _retired_token("var(--muted)", "var", r"var\(--muted\)", ("var(--muted-subtle)",)),
    _retired_token("var(--ring)", "var", r"var\(--ring\)"),
    _retired_token("var(--destructive)", "var", r"var\(--destructive\)"),
    _retired_token("var(--input)", "var", r"var\(--input\)"),
    _retired_token("var(--primary-hover)", "var", r"var\(--primary-hover\)"),
    _retired_token("var(--primary-05)", "var", r"var\(--primary-05\)"),
    _retired_token("var(--primary-08)", "var", r"var\(--primary-08\)"),
    _retired_token("var(--primary-10)", "var", r"var\(--primary-10\)"),
    _retired_token("var(--primary-12)", "var", r"var\(--primary-12\)"),
    _retired_token("var(--muted-subtle)", "var", r"var\(--muted-subtle\)"),
    _retired_token(
        "var(--surface)",
        "var",
        r"var\(--surface\)",
        ("var(--surface-primary)", "var(--surface-secondary)"),
    ),
    _retired_token("var(--surface-elevated)", "var", r"var\(--surface-elevated\)"),
    _retired_token("var(--error)", "var", r"var\(--error\)", ("var(--error-hover)",)),
    _retired_token("var(--error-hover)", "var", r"var\(--error-hover\)"),
    _retired_token("var(--success)", "var", r"var\(--success\)"),
    _retired_token("var(--warning)", "var", r"var\(--warning\)"),
    _retired_token("var(--running)", "var", r"var\(--running\)"),
)


def _marker_hits(source: str, markers: Iterable[str | re.Pattern[str]]) -> list[str]:
    hits: list[str] = []

    for line_number, line in enumerate(source.splitlines(), start=1):
        for marker in markers:
            if isinstance(marker, str):
                matched = marker in line
            else:
                matched = marker.search(line) is not None
            if matched:
                hits.append(f"{line_number}: {line.strip()}")

    return hits


def _e2e_source_files(root: Path) -> list[SourceFile]:
    return [
        SourceFile(
            relative_path=path.relative_to(E2E_TESTS).as_posix(),
            path=path,
            source=_read(path),
        )
        for path in _walk_files(root)
        if re.search(r"\.[cm]?tsx?$", path.name)
    ]


def _import_path_for_e2e_helper(relative_path: str) -> str:
    path_without_extension = re.sub(r"\.[cm]?tsx?$", "", relative_path)

    if path_without_extension.startswith("helpers/"):
        return "./" + path_without_extension
    if path_without_extension.startswith("fixtures/"):
        return "./" + path_without_extension
    return path_without_extension


def _ui_package_exports() -> dict[str, object]:
    package_json = json.loads(_read(UI_PACKAGE_JSON))
    return package_json.get("exports", {})


def _collect_gui_ui_imports() -> list[tuple[Path, str]]:
    import_pattern = re.compile(r"from\s+[\"']@runsight/ui/([^\"']+)[\"']")

    return [
        (path, f"./{match.group(1)}")
        for path in _runtime_gui_sources()
        for match in import_pattern.finditer(_read(path))
    ]


def _collect_cn_imports() -> list[tuple[Path, str, str]]:
    import_pattern = re.compile(
        r"import\s+(?:type\s+)?([\s\S]*?)\s+from\s+[\"']([^\"']+)[\"'];?",
        flags=re.MULTILINE,
    )

    imports: list[tuple[Path, str, str]] = []
    for path in _runtime_gui_sources():
        for match in import_pattern.finditer(_read(path)):
            clause, import_path = match.groups()
            if re.search(r"\bcn\b", clause):
                imports.append((path, clause.strip(), import_path))

    return imports


def _duplicate_cn_export_paths() -> list[Path]:
    candidate_paths = (
        GUI_SRC / "lib" / "utils.ts",
        GUI_SRC / "utils" / "helpers.ts",
    )

    return [
        path
        for path in candidate_paths
        if path.exists() and re.search(r"export\s+(?:function|const)\s+cn\b", _read(path))
    ]


def test_gui_typescript_build_graph_is_entrypoint_owned() -> None:
    tsconfig = json.loads(_read(GUI_ROOT / "tsconfig.json"))
    includes = tsconfig.get("include", [])
    excludes = set(tsconfig.get("exclude", []))

    assert includes == ["src/main.tsx", "src/vite-env.d.ts"]
    assert "src/**/*.stories.ts" in excludes
    assert "src/**/*.stories.tsx" in excludes
    assert "src/**/*.test.ts" in excludes
    assert "src/**/*.test.tsx" in excludes
    assert "src/**/__tests__/**" in excludes


def test_canonical_flows_ui_does_not_read_phantom_workflow_response_fields() -> None:
    failures: list[str] = []

    for path in WORKFLOW_RESPONSE_SOURCES:
        source = _read(path)
        for field in PHANTOM_WORKFLOW_FIELDS:
            pattern = re.compile(rf"\b(?:workflow|w|a|b)\.{field}\b")
            hits = _marker_hits(source, [pattern])
            if hits:
                failures.append(
                    f"{_relative(path)} reads phantom WorkflowResponse field {field}:\n"
                    + "\n".join(hits)
                )

    assert not failures, "\n\n".join(failures)


@pytest.mark.parametrize("token", RETIRED_TOKENS, ids=lambda token: token.name)
def test_retired_gui_token_detector_matches_only_the_retired_token(token: RetiredToken) -> None:
    assert token.pattern.search(token.name)

    for safe_sample in token.safe_samples:
        assert not token.pattern.search(safe_sample), safe_sample


def test_shipped_gui_screen_sources_do_not_use_retired_design_tokens() -> None:
    failures: list[str] = []

    for relative_path in TOKEN_SWEEP_FILES:
        path = GUI_SRC / relative_path
        if not path.exists():
            failures.append(f"{relative_path} is missing from the retained screen token sweep.")
            continue

        source = _read(path)
        for token in RETIRED_TOKENS:
            if token.pattern.search(source):
                failures.append(f"{relative_path}: retired {token.kind} token {token.name}")

    assert not failures, "\n".join(failures)


def test_readonly_surface_browser_spec_uses_e2e_fixture_owners() -> None:
    e2e_source = _read(E2E_READONLY_SPEC)
    readonly_fixture_name = re.compile(
        r"(?:^|/)(?:readonly[-A-Za-z0-9]*surface|surface[-A-Za-z0-9]*readonly|"
        r"readonly[-A-Za-z0-9]*run|run[-A-Za-z0-9]*readonly)"
        r"[-A-Za-z0-9]*\.[cm]?tsx?$"
    )
    readonly_fixture_source = re.compile(
        r"readonly surface fixture|readonly run fixture|readonly canvas fixture|"
        r"seedReadonly(?:Run|Canvas)Fixture",
        flags=re.I,
    )
    readonly_fixture_owners = [
        source_file
        for root in (E2E_TESTS / "fixtures", E2E_TESTS / "helpers")
        for source_file in _e2e_source_files(root)
        if readonly_fixture_name.search(source_file.relative_path)
        or readonly_fixture_source.search(source_file.source)
    ]
    used_fixture_owners = [
        source_file
        for source_file in readonly_fixture_owners
        if _import_path_for_e2e_helper(source_file.relative_path) in e2e_source
    ]
    forbidden_fixture_seeding = _marker_hits(
        e2e_source,
        (
            "execFileSync",
            "runsight.db",
            re.compile(r"INSERT(?:\s+OR\s+REPLACE)?\s+INTO", flags=re.I),
            re.compile(r"DELETE\s+FROM", flags=re.I),
            "resolveE2ERuntimePath",
            re.compile(r"[\"']\.canvas[\"']"),
            "SEEDED_WORKFLOW_YAML",
            "SEEDED_CANVAS_STATE",
        ),
    )

    failures: list[str] = []
    if not readonly_fixture_owners:
        failures.append(
            "Expected named readonly fixture owner files under E2E helpers or fixtures."
        )
    if not used_fixture_owners:
        failures.append(
            "Expected readonly-surface.spec.ts to import a named readonly fixture owner."
        )
    if forbidden_fixture_seeding:
        failures.append(
            "readonly-surface.spec.ts must not seed DB/canvas/YAML fixtures directly:\n"
            + "\n".join(forbidden_fixture_seeding)
        )

    assert not failures, "\n\n".join(failures)


def test_surface_workspace_rename_and_run_table_boundaries_are_static() -> None:
    expected_existing_paths = (
        GUI_SRC / "features" / "surface" / "__tests__",
        GUI_SRC / "features" / "surface" / "__tests__" / "yamlParser.test.ts",
        GUI_SRC
        / "features"
        / "surface"
        / "__tests__"
        / "yamlCompilerSerializationFiltering.test.ts",
        GUI_SRC / "features" / "surface" / "WorkflowSurface.tsx",
        GUI_SRC / "features" / "surface" / "SurfaceShell.tsx",
        GUI_SRC / "features" / "surface" / "SurfaceYamlEditor.tsx",
        GUI_SRC / "features" / "surface" / "surfaceContract.ts",
        GUI_SRC / "features" / "surface" / "useSurfaceHeaderSlots.tsx",
        REPO_ROOT / "packages" / "ui" / "RunStatusDot.tsx",
        REPO_ROOT / "packages" / "ui" / "runTable.styles.ts",
    )
    expected_missing_paths = (
        GUI_SRC / "features" / "surface" / "yamlSync.test.ts",
        GUI_SRC / "features" / "canvas" / "yamlSync.test.ts",
        GUI_SRC / "features" / "surface" / "LazyMonacoEditor.tsx",
        GUI_SRC / "features" / "canvas",
        GUI_SRC / "features" / "runs" / "RunStatusDot.tsx",
        GUI_SRC / "features" / "runs" / "runTable.styles.ts",
    )
    failures = [
        f"{_relative(path)} is missing." for path in expected_existing_paths if not path.exists()
    ]
    failures.extend(
        f"{_relative(path)} should not exist." for path in expected_missing_paths if path.exists()
    )

    canvas_shell_import_patterns = [
        re.compile(
            r"^\s*import\s+.*\b(CanvasTopbar|CanvasBottomPanel|CanvasStatusBar|WorkflowCanvas)\b"
        )
    ]
    canvas_shell_import_hits = [
        hit
        for path in _runtime_gui_sources(GUI_SRC / "features")
        for hit in _line_hits(path, canvas_shell_import_patterns)
    ]
    if canvas_shell_import_hits:
        failures.append(
            "Live GUI feature source must not import retired canvas-prefixed shell names:\n"
            + "\n".join(canvas_shell_import_hits)
        )

    routes_source = _read(GUI_SRC / "routes" / "index.tsx")
    if 'from "@/features/surface/WorkflowSurface"' not in routes_source:
        failures.append("routes/index.tsx must import WorkflowSurface from features/surface.")
    if "@/features/canvas/WorkflowSurface" in routes_source:
        failures.append("routes/index.tsx must not import WorkflowSurface from features/canvas.")

    runs_files = [
        path.relative_to(GUI_SRC).as_posix()
        for path in _walk_files(GUI_SRC / "features" / "runs")
        if "__tests__" not in path.parts
    ]
    if sorted(runs_files) != [
        "features/runs/RunRow.tsx",
        "features/runs/RunsPage.tsx",
        "features/runs/RunsTab.tsx",
    ]:
        failures.append(
            "features/runs should contain only RunRow.tsx, RunsPage.tsx, and RunsTab.tsx; "
            f"found: {sorted(runs_files)}"
        )

    runs_page_source = _read(GUI_SRC / "features" / "runs" / "RunsPage.tsx")
    for required_pattern in (
        re.compile(r"from\s+[\"']\./RunsTab[\"']"),
        re.compile(r"from\s+[\"']\./RunRow[\"']"),
        re.compile(r"import\s+\{\s*PageHeader\s*\}"),
    ):
        if not required_pattern.search(runs_page_source):
            failures.append(f"RunsPage.tsx is missing {required_pattern.pattern!r}.")
    if re.search(r"from\s+[\"']\./RunsTable[\"']", runs_page_source):
        failures.append("RunsPage.tsx must not import retired RunsTable.")

    runs_tab_source = _read(GUI_SRC / "features" / "runs" / "RunsTab.tsx")
    if "PageHeader" in runs_tab_source:
        failures.append("RunsTab.tsx must not own outer page header chrome.")
    if "useRuns(" not in runs_tab_source:
        failures.append("RunsTab.tsx should own the useRuns table query.")
    if "RUN_COLUMNS" not in runs_tab_source:
        failures.append("RunsTab.tsx should keep run-table column ownership.")

    assert not failures, "\n".join(failures)


def test_gui_cn_imports_converge_on_packages_ui_utils() -> None:
    cn_imports = _collect_cn_imports()
    local_imports = [
        (path, import_path)
        for path, _clause, import_path in cn_imports
        if import_path in {"@/utils/helpers", "@/lib/utils"}
    ]
    non_ui_imports = [
        (path, import_path)
        for path, _clause, import_path in cn_imports
        if not re.match(r"^@runsight/ui(?:/|$)", import_path)
    ]
    ui_imports = [
        (path, import_path)
        for path, _clause, import_path in cn_imports
        if re.match(r"^@runsight/ui(?:/|$)", import_path)
    ]
    duplicate_cn_exports = _duplicate_cn_export_paths()
    failures: list[str] = []

    if local_imports:
        failures.append(
            "GUI cn consumers must not import from local helper paths:\n"
            + "\n".join(
                f"{_relative(path)} -> {import_path}" for path, import_path in local_imports
            )
        )
    if non_ui_imports:
        failures.append(
            "GUI cn consumers must use a packages/ui-owned import path:\n"
            + "\n".join(
                f"{_relative(path)} -> {import_path}" for path, import_path in non_ui_imports
            )
        )
    if not ui_imports:
        failures.append("Expected at least one GUI runtime cn import from @runsight/ui.")
    if duplicate_cn_exports:
        failures.append(
            "Duplicate apps/gui cn helper exports must be deleted:\n"
            + "\n".join(_relative(path) for path in duplicate_cn_exports)
        )

    assert not failures, "\n\n".join(failures)


def test_gui_runtime_uses_only_explicit_packages_ui_exports() -> None:
    exports_map = _ui_package_exports()
    explicit_exports = {
        subpath for subpath in exports_map if subpath not in {"./*", "./styles.css"}
    }
    unsupported_imports = [
        (path, subpath)
        for path, subpath in _collect_gui_ui_imports()
        if subpath not in explicit_exports
    ]

    assert "./*" not in exports_map
    assert not unsupported_imports, "\n".join(
        f"{_relative(path)} -> {subpath}" for path, subpath in unsupported_imports
    )
