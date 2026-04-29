"""Red tests for RUN-825: mandatory embedded identity on tool and assertion manifests."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml
from pydantic import ValidationError


def _write_tool_fixture(
    base_dir: Path,
    *,
    stem: str = "lookup_profile",
    manifest_id: str = "lookup_profile",
    kind: str = "tool",
) -> Path:
    tools_dir = base_dir / "custom" / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": "1.0",
        "id": manifest_id,
        "kind": kind,
        "type": "custom",
        "executor": "python",
        "name": "Lookup Profile",
        "description": "Looks up a profile.",
        "parameters": {"type": "object"},
        "code": dedent(
            """\
            def main(args):
                return args
            """
        ),
    }

    path = tools_dir / f"{stem}.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _write_assertion_fixture(
    base_dir: Path,
    *,
    stem: str = "budget_guard",
    manifest_id: str = "budget_guard",
    kind: str = "assertion",
) -> Path:
    assertions_dir = base_dir / "custom" / "assertions"
    assertions_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": "1.0",
        "id": manifest_id,
        "kind": kind,
        "name": "Budget Guard",
        "description": "Keeps cost under budget.",
        "returns": "bool",
        "source": "budget_guard.py",
    }

    source_path = assertions_dir / "budget_guard.py"
    source_path.write_text(
        dedent(
            """\
            def get_assert(output, context):
                return True
            """
        ),
        encoding="utf-8",
    )

    path = assertions_dir / f"{stem}.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


class TestToolManifestIdentityContract:
    def test_tool_manifest_requires_embedded_id_and_kind(self):
        from runsight_core.yaml.discovery._tool import ToolManifest

        manifest = ToolManifest.model_validate(
            {
                "version": "1.0",
                "id": "lookup_profile",
                "kind": "tool",
                "type": "custom",
                "executor": "python",
                "name": "Lookup Profile",
                "description": "Looks up a profile.",
                "parameters": {"type": "object"},
                "code": "def main(args):\n    return args\n",
            }
        )

        assert manifest.id == "lookup_profile"
        assert manifest.kind == "tool"

    @pytest.mark.parametrize("missing_field", ["id", "kind"])
    def test_tool_manifest_rejects_missing_required_identity_field(self, missing_field: str):
        from runsight_core.yaml.discovery._tool import ToolManifest

        raw = {
            "version": "1.0",
            "id": "lookup_profile",
            "kind": "tool",
            "type": "custom",
            "executor": "python",
            "name": "Lookup Profile",
            "description": "Looks up a profile.",
            "parameters": {"type": "object"},
            "code": "def main(args):\n    return args\n",
        }
        raw.pop(missing_field)

        with pytest.raises(ValidationError) as exc_info:
            ToolManifest.model_validate(raw)

        error_locs = {tuple(error["loc"]) for error in exc_info.value.errors()}
        assert (missing_field,) in error_locs

    def test_tool_manifest_rejects_wrong_kind_value(self):
        from runsight_core.yaml.discovery._tool import ToolManifest

        with pytest.raises(ValidationError, match=r"kind.*tool"):
            ToolManifest.model_validate(
                {
                    "version": "1.0",
                    "id": "lookup_profile",
                    "kind": "assertion",
                    "type": "custom",
                    "executor": "python",
                    "name": "Lookup Profile",
                    "description": "Looks up a profile.",
                    "parameters": {"type": "object"},
                    "code": "def main(args):\n    return args\n",
                }
            )

    def test_tool_scanner_rejects_filename_stem_mismatch(self, tmp_path: Path):
        _write_tool_fixture(tmp_path, stem="lookup_profile", manifest_id="embedded_tool")

        from runsight_core.yaml.discovery import ToolScanner

        with pytest.raises(
            ValueError, match=r"embedded_tool.*lookup_profile|lookup_profile.*embedded_tool"
        ):
            ToolScanner(tmp_path).scan()

    def test_tool_scanner_rejects_suffix_embedded_filename_stem_mismatch(self, tmp_path: Path):
        _write_tool_fixture(
            tmp_path,
            stem="lookup_profile",
            manifest_id="lookup_profile_embedded",
        )

        from runsight_core.yaml.discovery import ToolScanner

        with pytest.raises(
            ValueError,
            match=r"lookup_profile_embedded.*lookup_profile|lookup_profile.*lookup_profile_embedded",
        ):
            ToolScanner(tmp_path).scan()

    def test_tool_meta_uses_embedded_id_with_matching_filename(self, tmp_path: Path):
        _write_tool_fixture(tmp_path, stem="embedded_tool", manifest_id="embedded_tool")

        from runsight_core.yaml.discovery import ToolScanner

        index = ToolScanner(tmp_path).scan().ids()

        assert "embedded_tool" in index
        meta = index["embedded_tool"]
        assert meta.tool_id == "embedded_tool"
        assert meta.file_path.name == "embedded_tool.yaml"

    def test_tool_scan_index_does_not_resolve_path_aliases(self, tmp_path: Path):
        _write_tool_fixture(tmp_path, stem="embedded_tool", manifest_id="embedded_tool")

        from runsight_core.yaml.discovery import ToolScanner

        index = ToolScanner(tmp_path).scan()
        relative_ref = "custom/tools/embedded_tool.yaml"
        absolute_ref = (tmp_path / relative_ref).resolve().as_posix()

        assert index.get("embedded_tool") is not None
        assert index.get(relative_ref) is None
        assert index.get(absolute_ref) is None

    def test_tool_scanner_rejects_invalid_embedded_id(self, tmp_path: Path):
        _write_tool_fixture(tmp_path, stem="lookup_profile", manifest_id="Bad-Tool")

        from runsight_core.yaml.discovery import ToolScanner

        with pytest.raises(ValueError, match=r"tool id|invalid"):
            ToolScanner(tmp_path).scan()

    def test_tool_scanner_rejects_reserved_embedded_id(self, tmp_path: Path):
        _write_tool_fixture(tmp_path, stem="lookup_profile", manifest_id="http")

        from runsight_core.yaml.discovery import ToolScanner

        with pytest.raises(ValueError, match=r"reserved builtin.*tool:http"):
            ToolScanner(tmp_path).scan()

    def test_tool_scanner_rejects_code_file_path_traversal(self, tmp_path: Path):
        tools_dir = tmp_path / "custom" / "tools"
        tools_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / "custom" / "evil.py").write_text(
            "def main(args):\n    return args\n",
            encoding="utf-8",
        )
        (tools_dir / "lookup_profile.yaml").write_text(
            yaml.safe_dump(
                {
                    "version": "1.0",
                    "id": "lookup_profile",
                    "kind": "tool",
                    "type": "custom",
                    "executor": "python",
                    "name": "Lookup Profile",
                    "description": "Looks up a profile.",
                    "parameters": {"type": "object"},
                    "code_file": "../evil.py",
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        from runsight_core.yaml.discovery import ToolScanner

        with pytest.raises(ValueError, match="escapes tool directory"):
            ToolScanner(tmp_path).scan()


class TestAssertionManifestIdentityContract:
    def test_assertion_manifest_requires_embedded_id_and_kind(self):
        from runsight_core.yaml.discovery._assertion import AssertionManifest

        manifest = AssertionManifest.model_validate(
            {
                "version": "1.0",
                "id": "budget_guard",
                "kind": "assertion",
                "name": "Budget Guard",
                "description": "Keeps cost under budget.",
                "returns": "bool",
                "source": "budget_guard.py",
            }
        )

        assert manifest.id == "budget_guard"
        assert manifest.kind == "assertion"

    @pytest.mark.parametrize("missing_field", ["id", "kind"])
    def test_assertion_manifest_rejects_missing_required_identity_field(self, missing_field: str):
        from runsight_core.yaml.discovery._assertion import AssertionManifest

        raw = {
            "version": "1.0",
            "id": "budget_guard",
            "kind": "assertion",
            "name": "Budget Guard",
            "description": "Keeps cost under budget.",
            "returns": "bool",
            "source": "budget_guard.py",
        }
        raw.pop(missing_field)

        with pytest.raises(ValidationError) as exc_info:
            AssertionManifest.model_validate(raw)

        error_locs = {tuple(error["loc"]) for error in exc_info.value.errors()}
        assert (missing_field,) in error_locs

    def test_assertion_manifest_rejects_wrong_kind_value(self):
        from runsight_core.yaml.discovery._assertion import AssertionManifest

        with pytest.raises(ValidationError, match=r"kind.*assertion"):
            AssertionManifest.model_validate(
                {
                    "version": "1.0",
                    "id": "budget_guard",
                    "kind": "tool",
                    "name": "Budget Guard",
                    "description": "Keeps cost under budget.",
                    "returns": "bool",
                    "source": "budget_guard.py",
                }
            )

    def test_assertion_scanner_rejects_filename_stem_mismatch(self, tmp_path: Path):
        _write_assertion_fixture(tmp_path, stem="budget_guard", manifest_id="embedded_assertion")

        from runsight_core.yaml.discovery import AssertionScanner

        with pytest.raises(
            ValueError, match=r"embedded_assertion.*budget_guard|budget_guard.*embedded_assertion"
        ):
            AssertionScanner(tmp_path).scan()

    def test_assertion_scanner_rejects_suffix_embedded_filename_stem_mismatch(self, tmp_path: Path):
        _write_assertion_fixture(
            tmp_path,
            stem="budget_guard",
            manifest_id="budget_guard_embedded",
        )

        from runsight_core.yaml.discovery import AssertionScanner

        with pytest.raises(
            ValueError,
            match=r"budget_guard_embedded.*budget_guard|budget_guard.*budget_guard_embedded",
        ):
            AssertionScanner(tmp_path).scan()

    def test_assertion_meta_uses_embedded_id_with_matching_filename(self, tmp_path: Path):
        _write_assertion_fixture(
            tmp_path, stem="embedded_assertion", manifest_id="embedded_assertion"
        )

        from runsight_core.yaml.discovery import AssertionScanner

        index = AssertionScanner(tmp_path).scan().ids()

        assert "embedded_assertion" in index
        meta = index["embedded_assertion"]
        assert meta.assertion_id == "embedded_assertion"
        assert meta.file_path.name == "embedded_assertion.yaml"

    def test_assertion_scan_index_does_not_resolve_path_aliases(self, tmp_path: Path):
        _write_assertion_fixture(
            tmp_path, stem="embedded_assertion", manifest_id="embedded_assertion"
        )

        from runsight_core.yaml.discovery import AssertionScanner

        index = AssertionScanner(tmp_path).scan()
        relative_ref = "custom/assertions/embedded_assertion.yaml"
        absolute_ref = (tmp_path / relative_ref).resolve().as_posix()

        assert index.get("embedded_assertion") is not None
        assert index.get(relative_ref) is None
        assert index.get(absolute_ref) is None

    def test_assertion_scanner_rejects_invalid_embedded_id(self, tmp_path: Path):
        _write_assertion_fixture(tmp_path, stem="budget_guard", manifest_id="Bad-Assertion")

        from runsight_core.yaml.discovery import AssertionScanner

        with pytest.raises(ValueError, match=r"assertion id|invalid"):
            AssertionScanner(tmp_path).scan()

    def test_assertion_scanner_rejects_source_path_traversal(self, tmp_path: Path):
        assertions_dir = tmp_path / "custom" / "assertions"
        assertions_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / "custom" / "evil.py").write_text(
            "def get_assert(output, context):\n    return True\n",
            encoding="utf-8",
        )
        (assertions_dir / "budget_guard.yaml").write_text(
            yaml.safe_dump(
                {
                    "version": "1.0",
                    "id": "budget_guard",
                    "kind": "assertion",
                    "name": "Budget Guard",
                    "description": "Keeps cost under budget.",
                    "returns": "bool",
                    "source": "../evil.py",
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        from runsight_core.yaml.discovery import AssertionScanner

        with pytest.raises(ValueError, match="escapes assertion directory"):
            AssertionScanner(tmp_path).scan()

    def test_assertion_scanner_rejects_reserved_embedded_id(self, tmp_path: Path):
        _write_assertion_fixture(tmp_path, stem="budget_guard", manifest_id="contains")

        from runsight_core.yaml.discovery import AssertionScanner

        with pytest.raises(ValueError, match=r"reserved builtin.*assertion:contains"):
            AssertionScanner(tmp_path).scan()
