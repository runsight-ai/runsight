"""
Tests for the unified discovery surface.
"""

import importlib
import tempfile
from pathlib import Path
from textwrap import dedent

import pytest
from runsight_core.primitives import Soul


class TestPublicDiscoverySurface:
    """Legacy helpers should be removed while the scanner surface stays public."""

    def test_discovery_module_keeps_scanner_public_api(self):
        from runsight_core.yaml.discovery import SoulScanner, ToolScanner, WorkflowScanner

        assert SoulScanner is not None
        assert ToolScanner is not None
        assert WorkflowScanner is not None

    @pytest.mark.parametrize(
        "legacy_helper_name",
        [
            "discover_custom_assets",
            "_to_snake_case",
            "_discover_blocks",
            "_discover_workflows",
        ],
    )
    def test_legacy_discovery_helpers_are_removed_from_public_module(self, legacy_helper_name):
        import runsight_core.yaml.discovery as discovery_module

        assert not hasattr(
            discovery_module,
            legacy_helper_name,
        ), f"Legacy helper {legacy_helper_name} should be removed from runsight_core.yaml.discovery"

    def test_yaml_package_no_longer_exports_discover_custom_assets(self):
        import runsight_core.yaml as yaml_module

        assert not hasattr(yaml_module, "discover_custom_assets")


class TestDiscoverSouls:
    """Tests for soul discovery from YAML files."""

    def test_discover_souls_empty_directory(self):
        """AC-1: Empty custom/souls directory returns empty dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            souls_dir = base_dir / "custom" / "souls"
            souls_dir.mkdir(parents=True)

            from runsight_core.yaml.discovery import SoulScanner

            souls = SoulScanner(base_dir).scan().stems()
            assert souls == {}

    def test_discover_souls_nonexistent_directory(self):
        """AC-2: Nonexistent custom/souls directory returns empty dict (no exception)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)

            from runsight_core.yaml.discovery import SoulScanner

            souls = SoulScanner(base_dir).scan().stems()
            assert souls == {}

    def test_discover_single_soul(self):
        """AC-3: Discover a single Soul from a custom/souls YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            souls_dir = base_dir / "custom" / "souls"
            souls_dir.mkdir(parents=True)

            soul_file = souls_dir / "custom_soul.yaml"
            soul_file.write_text(
                dedent("""
                id: custom_soul_1
                role: Custom Researcher
                system_prompt: You are a custom researcher
                """)
            )

            from runsight_core.yaml.discovery import SoulScanner

            souls = SoulScanner(base_dir).scan().stems()

            assert "custom_soul" in souls
            assert isinstance(souls["custom_soul"], Soul)
            assert souls["custom_soul"].id == "custom_soul_1"
            assert souls["custom_soul"].role == "Custom Researcher"

    def test_discover_multiple_souls(self):
        """AC-4: Discover multiple Souls from different custom/souls YAML files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            souls_dir = base_dir / "custom" / "souls"
            souls_dir.mkdir(parents=True)

            (souls_dir / "soul_a.yaml").write_text(
                dedent("""
                id: soul_a_1
                role: Role A
                system_prompt: Prompt A
                """)
            )

            (souls_dir / "soul_b.yaml").write_text(
                dedent("""
                id: soul_b_1
                role: Role B
                system_prompt: Prompt B
                """)
            )

            from runsight_core.yaml.discovery import SoulScanner

            souls = SoulScanner(base_dir).scan().stems()

            assert len(souls) == 2
            assert "soul_a" in souls
            assert "soul_b" in souls

    def test_discover_soul_with_tools(self):
        """AC-5: Discover Soul with optional tools field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            souls_dir = base_dir / "custom" / "souls"
            souls_dir.mkdir(parents=True)

            soul_file = souls_dir / "soul_with_tools.yaml"
            soul_file.write_text(
                dedent("""
                id: soul_with_tools_1
                role: Tool User
                system_prompt: You have tools
                tools:
                  - tool1
                """)
            )

            from runsight_core.yaml.discovery import SoulScanner

            souls = SoulScanner(base_dir).scan().stems()

            assert "soul_with_tools" in souls
            assert souls["soul_with_tools"].tools is not None
            assert len(souls["soul_with_tools"].tools) == 1

    def test_discover_soul_ignores_inline_override_keys(self):
        """AC-6: ignore_keys filters stems that are overridden inline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            souls_dir = base_dir / "custom" / "souls"
            souls_dir.mkdir(parents=True)

            (souls_dir / "overridden_soul.yaml").write_text(
                dedent("""
                id: overridden_soul_1
                role: Overridden Soul
                system_prompt: This should be ignored when overridden inline.
                """)
            )
            (souls_dir / "kept_soul.yaml").write_text(
                dedent("""
                id: kept_soul_1
                role: Kept Soul
                system_prompt: This should remain visible.
                """)
            )

            from runsight_core.yaml.discovery import SoulScanner

            souls = SoulScanner(base_dir).scan(ignore_keys={"overridden_soul"}).stems()

            assert "overridden_soul" not in souls
            assert "kept_soul" in souls

    def test_legacy_discover_souls_helper_is_removed_from_public_module(self):
        """AC-7: The public discovery surface should not expose _discover_souls anymore."""
        import runsight_core.yaml.discovery as discovery_module

        assert not hasattr(
            discovery_module,
            "_discover_souls",
        ), "Legacy _discover_souls helper should be removed from runsight_core.yaml.discovery"


class TestDiscoverCustomTools:
    """RUN-578: discovery of canonical custom tool files under custom/tools/."""

    @staticmethod
    def _load_symbols():
        from runsight_core.yaml.discovery import ToolMeta, ToolScanner

        def _scan_tools(base_dir: Path):
            return ToolScanner(base_dir).scan().stems()

        return _scan_tools, ToolMeta

    @staticmethod
    def _load_module():
        import runsight_core.yaml.discovery as discovery_module

        return discovery_module

    def test_tool_scanner_and_reserved_builtin_ids_are_publicly_importable(self):
        from runsight_core.yaml.discovery import RESERVED_BUILTIN_TOOL_IDS, ToolMeta, ToolScanner

        tool_module = importlib.import_module("runsight_core.yaml.discovery._tool")

        assert ToolScanner is not None
        assert ToolMeta is not None
        assert RESERVED_BUILTIN_TOOL_IDS == frozenset({"http", "file_io", "delegate"})
        assert ToolScanner.__module__ == tool_module.ToolScanner.__module__
        assert ToolMeta.__module__ == tool_module.ToolMeta.__module__
        assert RESERVED_BUILTIN_TOOL_IDS is tool_module.RESERVED_BUILTIN_TOOL_IDS

    def test_legacy_discover_custom_tools_helper_is_removed_from_public_module(self):
        discovery_module = self._load_module()

        assert not hasattr(
            discovery_module,
            "discover_custom_tools",
        ), "Legacy discover_custom_tools helper should be removed from runsight_core.yaml.discovery"

    @pytest.mark.parametrize(
        "legacy_helper_name",
        [
            "_validate_tool_main_contract",
            "_fail_tool_file",
            "_require_string",
            "_require_mapping",
            "_read_tool_code_file",
            "_normalize_request_config",
        ],
    )
    def test_legacy_tool_helpers_are_removed_from_public_module(self, legacy_helper_name):
        discovery_module = self._load_module()

        assert not hasattr(
            discovery_module,
            legacy_helper_name,
        ), f"Legacy helper {legacy_helper_name} should move out of runsight_core.yaml.discovery"

    def test_missing_custom_tools_directory_returns_empty_dict(self):
        scan_tools, _ = self._load_symbols()
        assert callable(scan_tools), "Expected custom tool scan helper to exist"

        with tempfile.TemporaryDirectory() as tmpdir:
            result = scan_tools(Path(tmpdir))
            assert result == {}

    def test_discovers_python_and_request_executor_tool_files_by_filename_stem(self):
        scan_tools, tool_meta = self._load_symbols()
        assert callable(scan_tools), "Expected custom tool scan helper to exist"
        assert tool_meta is not None, "Expected runsight_core.yaml.discovery.ToolMeta to exist"

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            tools_dir = base_dir / "custom" / "tools"
            tools_dir.mkdir(parents=True)

            (tools_dir / "python_helper.yaml").write_text(
                dedent("""
                version: "1.0"
                type: custom
                executor: python
                name: Python Helper
                description: Echo values back to the caller.
                parameters:
                  type: object
                  properties:
                    value:
                      type: string
                  required:
                    - value
                code: |
                  def main(args):
                      return args
                """)
            )
            (tools_dir / "request_lookup.yaml").write_text(
                dedent("""
                version: "1.0"
                type: custom
                executor: request
                name: Request Lookup
                description: Fetch data from a remote service.
                parameters:
                  type: object
                  properties:
                    user_id:
                      type: integer
                  required:
                    - user_id
                request:
                  method: GET
                  url: https://example.com/users/{{ user_id }}
                  headers:
                    X-Test: runsight
                  response_path: data.id
                timeout_seconds: 12
                """)
            )

            discovered = scan_tools(base_dir)

            assert set(discovered.keys()) == {"python_helper", "request_lookup"}
            assert isinstance(discovered["python_helper"], tool_meta)
            assert isinstance(discovered["request_lookup"], tool_meta)
            assert discovered["python_helper"].type == "custom"
            assert discovered["python_helper"].executor == "python"
            assert discovered["python_helper"].name == "Python Helper"
            assert discovered["request_lookup"].type == "custom"
            assert discovered["request_lookup"].executor == "request"
            assert discovered["request_lookup"].request["url"] == (
                "https://example.com/users/{{ user_id }}"
            )

    def test_legacy_type_http_is_rejected_with_file_specific_error(self):
        scan_tools, _ = self._load_symbols()
        assert callable(scan_tools), "Expected custom tool scan helper to exist"

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            tools_dir = base_dir / "custom" / "tools"
            tools_dir.mkdir(parents=True)
            invalid_file = tools_dir / "legacy_http.yaml"
            invalid_file.write_text(
                dedent("""
                version: "1.0"
                type: http
                """)
            )

            with pytest.raises(ValueError, match=r"legacy_http\.yaml.*type.*custom|legacy_http"):
                scan_tools(base_dir)

    def test_malformed_yaml_raises_file_specific_error(self):
        scan_tools, _ = self._load_symbols()
        assert callable(scan_tools), "Expected custom tool scan helper to exist"

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            tools_dir = base_dir / "custom" / "tools"
            tools_dir.mkdir(parents=True)
            invalid_file = tools_dir / "broken.yaml"
            invalid_file.write_text(
                'version: "1.0"\ntype: custom\nexecutor: python\ncode: [not: valid'
            )

            with pytest.raises(Exception, match="broken.yaml"):
                scan_tools(base_dir)

    def test_invalid_metadata_raises_file_specific_error(self):
        scan_tools, _ = self._load_symbols()
        assert callable(scan_tools), "Expected custom tool scan helper to exist"

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            tools_dir = base_dir / "custom" / "tools"
            tools_dir.mkdir(parents=True)
            invalid_file = tools_dir / "missing_executor.yaml"
            invalid_file.write_text(
                dedent("""
                version: "1.0"
                type: custom
                name: Missing Executor
                description: Broken metadata.
                parameters:
                  type: object
                code: |
                  def main(args):
                      return args
                """)
            )

            with pytest.raises(ValueError, match="missing_executor.yaml"):
                scan_tools(base_dir)

    def test_custom_tool_rejects_both_code_and_code_file(self):
        scan_tools, _ = self._load_symbols()
        assert callable(scan_tools), "Expected custom tool scan helper to exist"

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            tools_dir = base_dir / "custom" / "tools"
            tools_dir.mkdir(parents=True)
            invalid_file = tools_dir / "double_code.yaml"
            invalid_file.write_text(
                dedent("""
                version: "1.0"
                type: custom
                executor: python
                name: Double Code
                description: Declares both code and code_file.
                parameters:
                  type: object
                code: |
                  def main(args):
                      return args
                code_file: helper.py
                """)
            )

            with pytest.raises(ValueError, match="double_code.yaml"):
                scan_tools(base_dir)

    def test_custom_tool_rejects_missing_code_file(self):
        scan_tools, _ = self._load_symbols()
        assert callable(scan_tools), "Expected custom tool scan helper to exist"

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            tools_dir = base_dir / "custom" / "tools"
            tools_dir.mkdir(parents=True)
            invalid_file = tools_dir / "missing_code_file.yaml"
            invalid_file.write_text(
                dedent("""
                version: "1.0"
                type: custom
                executor: python
                name: Missing Code File
                description: References a file that does not exist.
                parameters:
                  type: object
                code_file: missing_impl.py
                """)
            )

            with pytest.raises(ValueError, match="missing_code_file.yaml"):
                scan_tools(base_dir)

    def test_custom_tool_rejects_unreadable_code_file(self):
        scan_tools, _ = self._load_symbols()
        assert callable(scan_tools), "Expected custom tool scan helper to exist"

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            tools_dir = base_dir / "custom" / "tools"
            tools_dir.mkdir(parents=True)
            (tools_dir / "impl_dir.py").mkdir()
            invalid_file = tools_dir / "unreadable_code_file.yaml"
            invalid_file.write_text(
                dedent("""
                version: "1.0"
                type: custom
                executor: python
                name: Unreadable Code File
                description: Points at an unreadable code file.
                parameters:
                  type: object
                code_file: impl_dir.py
                """)
            )

            with pytest.raises(ValueError, match=r"unreadable_code_file\.yaml"):
                scan_tools(base_dir)

    def test_custom_tool_rejects_invalid_main_signature(self):
        scan_tools, _ = self._load_symbols()
        assert callable(scan_tools), "Expected custom tool scan helper to exist"

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            tools_dir = base_dir / "custom" / "tools"
            tools_dir.mkdir(parents=True)
            invalid_file = tools_dir / "bad_signature.yaml"
            invalid_file.write_text(
                dedent("""
                version: "1.0"
                type: custom
                executor: python
                name: Bad Signature
                description: Uses the wrong main() signature.
                parameters:
                  type: object
                code: |
                  def main():
                      return {}
                """)
            )

            with pytest.raises(ValueError, match="bad_signature.yaml"):
                scan_tools(base_dir)

    def test_request_executor_requires_request_url(self):
        scan_tools, _ = self._load_symbols()
        assert callable(scan_tools), "Expected custom tool scan helper to exist"

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            tools_dir = base_dir / "custom" / "tools"
            tools_dir.mkdir(parents=True)
            invalid_file = tools_dir / "missing_request_url.yaml"
            invalid_file.write_text(
                dedent("""
                version: "1.0"
                type: custom
                executor: request
                name: Missing Request URL
                description: Missing nested request.url.
                parameters:
                  type: object
                request:
                  method: GET
                """)
            )

            with pytest.raises(ValueError, match=r"missing_request_url\.yaml"):
                scan_tools(base_dir)

    def test_request_executor_rejects_python_fields(self):
        scan_tools, _ = self._load_symbols()
        assert callable(scan_tools), "Expected custom tool scan helper to exist"

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            tools_dir = base_dir / "custom" / "tools"
            tools_dir.mkdir(parents=True)
            invalid_file = tools_dir / "request_with_code.yaml"
            invalid_file.write_text(
                dedent("""
                version: "1.0"
                type: custom
                executor: request
                name: Request With Code
                description: Request tools must not declare Python fields.
                parameters:
                  type: object
                code: |
                  def main(args):
                      return args
                request:
                  method: GET
                  url: https://example.com/users/{{ user_id }}
                """)
            )

            with pytest.raises(ValueError, match=r"request_with_code\.yaml"):
                scan_tools(base_dir)

    def test_python_executor_rejects_request_fields(self):
        scan_tools, _ = self._load_symbols()
        assert callable(scan_tools), "Expected custom tool scan helper to exist"

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            tools_dir = base_dir / "custom" / "tools"
            tools_dir.mkdir(parents=True)
            invalid_file = tools_dir / "python_with_request.yaml"
            invalid_file.write_text(
                dedent("""
                version: "1.0"
                type: custom
                executor: python
                name: Python With Request
                description: Python tools must not declare request metadata.
                parameters:
                  type: object
                request:
                  method: GET
                  url: https://example.com/users/{{ user_id }}
                code: |
                  def main(args):
                      return args
                """)
            )

            with pytest.raises(ValueError, match=r"python_with_request\.yaml"):
                scan_tools(base_dir)

    def test_unknown_executor_raises_file_specific_error(self):
        scan_tools, _ = self._load_symbols()
        assert callable(scan_tools), "Expected custom tool scan helper to exist"

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            tools_dir = base_dir / "custom" / "tools"
            tools_dir.mkdir(parents=True)
            invalid_file = tools_dir / "unknown_executor.yaml"
            invalid_file.write_text(
                dedent("""
                version: "1.0"
                type: custom
                executor: shell
                name: Unknown Executor
                description: Unsupported executor.
                parameters:
                  type: object
                """)
            )

            with pytest.raises(ValueError, match=r"unknown_executor\.yaml"):
                scan_tools(base_dir)

    def test_duplicate_filename_derived_tool_id_raises_explicit_error(self, monkeypatch):
        scan_tools, _ = self._load_symbols()
        assert callable(scan_tools), "Expected custom tool scan helper to exist"

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            tools_dir = base_dir / "custom" / "tools"
            shadow_dir = base_dir / "shadow"
            tools_dir.mkdir(parents=True)
            shadow_dir.mkdir()

            primary_file = tools_dir / "duplicate_tool.yaml"
            shadow_file = shadow_dir / "duplicate_tool.yaml"
            tool_yaml = dedent("""
            version: "1.0"
            type: custom
            executor: python
            name: Duplicate Tool
            description: Detect duplicate file-backed tool ids.
            parameters:
              type: object
            code: |
              def main(args):
                  return args
            """)
            primary_file.write_text(tool_yaml, encoding="utf-8")
            shadow_file.write_text(tool_yaml, encoding="utf-8")

            original_glob = Path.glob

            def _fake_glob(self, pattern):
                if self == tools_dir and pattern == "*.yaml":
                    return [primary_file, shadow_file]
                return original_glob(self, pattern)

            monkeypatch.setattr(Path, "glob", _fake_glob)

            with pytest.raises(ValueError, match=r"duplicate_tool.*duplicate|collision"):
                scan_tools(base_dir)

    @pytest.mark.parametrize("reserved_tool_id", ["http", "file_io", "delegate"])
    def test_reserved_builtin_tool_ids_are_rejected_during_discovery(self, reserved_tool_id):
        scan_tools, _ = self._load_symbols()
        assert callable(scan_tools), "Expected custom tool scan helper to exist"

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            tools_dir = base_dir / "custom" / "tools"
            tools_dir.mkdir(parents=True)
            reserved_file = tools_dir / f"{reserved_tool_id}.yaml"
            reserved_file.write_text(
                dedent(f"""
                version: "1.0"
                type: custom
                executor: python
                name: Shadow {reserved_tool_id}
                description: Attempts to shadow the reserved builtin tool id.
                parameters:
                  type: object
                code: |
                  def main(args):
                      return args
                """),
                encoding="utf-8",
            )

            with pytest.raises(
                ValueError,
                match=rf"reserved builtin tool id '{reserved_tool_id}'|collision.*{reserved_tool_id}",
            ):
                scan_tools(base_dir)


class TestRepoPolicyForCustomTools:
    """RUN-525: repository policy should explicitly allow custom/tools assets."""

    def test_agents_policy_allows_custom_tools_directory(self):
        repo_policy = Path(__file__).resolve().parents[3] / "AGENTS.md"
        assert repo_policy.exists(), f"Expected repo policy at {repo_policy}"

        contents = repo_policy.read_text(encoding="utf-8")
        assert "custom/tools/" in contents or "- tools" in contents, (
            "AGENTS.md should explicitly allow custom/tools/ under the custom asset policy"
        )
