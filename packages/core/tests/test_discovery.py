"""
Tests for auto-discovery engine for custom blocks, souls, tasks, and workflows.

This module tests:
- Discovery of custom BaseBlock subclasses in Python files (with snake_case ID generation)
- Discovery of custom Soul definitions from YAML files
- Discovery of custom Workflow definitions from YAML files
- Graceful handling of missing/non-existent custom_dir
"""

import tempfile
from pathlib import Path
from textwrap import dedent

import pytest
from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Soul
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.discovery import _to_snake_case, discover_custom_assets


class SimpleBlock(BaseBlock):
    """Test block for discovery tests."""

    async def execute(self, state: WorkflowState) -> WorkflowState:
        return state.model_copy(
            update={"results": {**state.results, self.block_id: "simple_block_executed"}}
        )


class CustomTestBlock(BaseBlock):
    """Another test block with custom name."""

    async def execute(self, state: WorkflowState) -> WorkflowState:
        return state.model_copy(
            update={"results": {**state.results, self.block_id: "custom_test_executed"}}
        )


class TestSnakeCaseConversion:
    """Tests for the snake_case conversion utility."""

    def test_simple_class_name_to_snake_case(self):
        """AC-1: Convert CamelCase to snake_case."""
        assert _to_snake_case("MyBlock") == "my_block"

    def test_single_word_to_snake_case(self):
        """AC-2: Single word (lowercase after 'S' in SimpleBlock)."""
        assert _to_snake_case("SimpleBlock") == "simple_block"

    def test_consecutive_caps_to_snake_case(self):
        """AC-3: Consecutive uppercase letters."""
        assert _to_snake_case("HTTPBlock") == "h_t_t_p_block"

    def test_all_caps_to_snake_case(self):
        """AC-4: All uppercase word."""
        assert _to_snake_case("ID") == "i_d"


class TestDiscoverBlocks:
    """Tests for block discovery from Python files."""

    def test_discover_blocks_empty_directory(self):
        """AC-1: Empty blocks directory returns empty dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir)
            blocks_dir = custom_dir / "blocks"
            blocks_dir.mkdir()

            blocks, _, _ = discover_custom_assets(custom_dir)
            assert blocks == {}

    def test_discover_blocks_nonexistent_directory(self):
        """AC-2: Nonexistent blocks directory returns empty dict (no exception)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir)

            blocks, _, _ = discover_custom_assets(custom_dir)
            assert blocks == {}

    def test_discover_single_custom_block(self):
        """AC-3: Discover a single BaseBlock subclass from a Python file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir)
            blocks_dir = custom_dir / "blocks"
            blocks_dir.mkdir()

            # Create a Python file with a BaseBlock subclass
            block_file = blocks_dir / "my_block.py"
            block_file.write_text(
                dedent("""
                from runsight_core.blocks.base import BaseBlock
                from runsight_core.state import WorkflowState

                class MyCustomBlock(BaseBlock):
                    async def execute(self, state: WorkflowState) -> WorkflowState:
                        return state.model_copy(
                            update={"results": {**state.results, self.block_id: "done"}}
                        )
                """)
            )

            blocks, _, _ = discover_custom_assets(custom_dir)

            assert "my_custom_block" in blocks
            assert issubclass(blocks["my_custom_block"], BaseBlock)
            assert blocks["my_custom_block"].__name__ == "MyCustomBlock"

    def test_discover_multiple_blocks_in_single_file(self):
        """AC-4: Discover multiple BaseBlock subclasses from one Python file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir)
            blocks_dir = custom_dir / "blocks"
            blocks_dir.mkdir()

            block_file = blocks_dir / "multi.py"
            block_file.write_text(
                dedent("""
                from runsight_core.blocks.base import BaseBlock
                from runsight_core.state import WorkflowState

                class FirstBlock(BaseBlock):
                    async def execute(self, state: WorkflowState) -> WorkflowState:
                        return state

                class SecondBlock(BaseBlock):
                    async def execute(self, state: WorkflowState) -> WorkflowState:
                        return state
                """)
            )

            blocks, _, _ = discover_custom_assets(custom_dir)

            assert "first_block" in blocks
            assert "second_block" in blocks
            assert len(blocks) == 2

    def test_discover_blocks_multiple_files(self):
        """AC-5: Discover blocks from multiple Python files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir)
            blocks_dir = custom_dir / "blocks"
            blocks_dir.mkdir()

            # First file
            (blocks_dir / "block_one.py").write_text(
                dedent("""
                from runsight_core.blocks.base import BaseBlock
                from runsight_core.state import WorkflowState

                class BlockOne(BaseBlock):
                    async def execute(self, state: WorkflowState) -> WorkflowState:
                        return state
                """)
            )

            # Second file
            (blocks_dir / "block_two.py").write_text(
                dedent("""
                from runsight_core.blocks.base import BaseBlock
                from runsight_core.state import WorkflowState

                class BlockTwo(BaseBlock):
                    async def execute(self, state: WorkflowState) -> WorkflowState:
                        return state
                """)
            )

            blocks, _, _ = discover_custom_assets(custom_dir)

            assert "block_one" in blocks
            assert "block_two" in blocks
            assert len(blocks) == 2

    def test_discover_blocks_snake_case_id_generation(self):
        """AC-6: Block IDs are generated in snake_case from class names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir)
            blocks_dir = custom_dir / "blocks"
            blocks_dir.mkdir()

            block_file = blocks_dir / "blocks.py"
            block_file.write_text(
                dedent("""
                from runsight_core.blocks.base import BaseBlock
                from runsight_core.state import WorkflowState

                class MyDataProcessorBlock(BaseBlock):
                    async def execute(self, state: WorkflowState) -> WorkflowState:
                        return state
                """)
            )

            blocks, _, _ = discover_custom_assets(custom_dir)

            assert "my_data_processor_block" in blocks


class TestDiscoverSouls:
    """Tests for soul discovery from YAML files."""

    def test_discover_souls_empty_directory(self):
        """AC-1: Empty custom/souls directory returns empty dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            souls_dir = base_dir / "custom" / "souls"
            souls_dir.mkdir(parents=True)

            from runsight_core.yaml.discovery._base import SoulScanner

            souls = SoulScanner(base_dir).scan().stems()
            assert souls == {}

    def test_discover_souls_nonexistent_directory(self):
        """AC-2: Nonexistent custom/souls directory returns empty dict (no exception)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)

            from runsight_core.yaml.discovery._base import SoulScanner

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

            from runsight_core.yaml.discovery._base import SoulScanner

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

            from runsight_core.yaml.discovery._base import SoulScanner

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

            from runsight_core.yaml.discovery._base import SoulScanner

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

            from runsight_core.yaml.discovery._base import SoulScanner

            souls = SoulScanner(base_dir).scan(ignore_keys={"overridden_soul"}).stems()

            assert "overridden_soul" not in souls
            assert "kept_soul" in souls


class TestDiscoverWorkflows:
    """Tests for workflow discovery from YAML files."""

    def test_discover_workflows_empty_directory(self):
        """AC-1: Empty workflows directory returns empty dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir)
            workflows_dir = custom_dir / "workflows"
            workflows_dir.mkdir()

            _, _, workflows = discover_custom_assets(custom_dir)
            assert workflows == {}

    def test_discover_workflows_nonexistent_directory(self):
        """AC-2: Nonexistent workflows directory returns empty dict (no exception)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir)

            _, _, workflows = discover_custom_assets(custom_dir)
            assert workflows == {}

    @pytest.mark.xfail(
        reason="RUN-570 removed inline souls; RUN-571 will wire library discovery", strict=True
    )
    def test_discover_single_workflow(self):
        """AC-3: Discover a single Workflow from a YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir)
            workflows_dir = custom_dir / "workflows"
            workflows_dir.mkdir()

            workflow_file = workflows_dir / "simple_workflow.yaml"
            workflow_file.write_text(
                dedent("""
                version: "1.0"
                config:
                  model_name: gpt-4o
                souls:
                  researcher:
                    id: researcher_1
                    role: Researcher
                    system_prompt: You research things.
                workflow:
                  name: test_workflow
                  entry: block1
                  transitions:
                    - from: block1
                      to: null
                blocks:
                  block1:
                    type: linear
                    soul_ref: researcher
                """)
            )

            _, _, workflows = discover_custom_assets(custom_dir)

            assert "simple_workflow" in workflows
            assert isinstance(workflows["simple_workflow"], Workflow)
            assert workflows["simple_workflow"].name == "test_workflow"

    @pytest.mark.xfail(
        reason="RUN-570 removed inline souls; RUN-571 will wire library discovery", strict=True
    )
    def test_discover_multiple_workflows(self):
        """AC-4: Discover multiple Workflows from different YAML files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir)
            workflows_dir = custom_dir / "workflows"
            workflows_dir.mkdir()

            (workflows_dir / "workflow_a.yaml").write_text(
                dedent("""
                version: "1.0"
                souls:
                  researcher:
                    id: researcher_1
                    role: Researcher
                    system_prompt: You research things.
                workflow:
                  name: workflow_a
                  entry: block1
                  transitions:
                    - from: block1
                      to: null
                blocks:
                  block1:
                    type: linear
                    soul_ref: researcher
                """)
            )

            (workflows_dir / "workflow_b.yaml").write_text(
                dedent("""
                version: "1.0"
                souls:
                  researcher:
                    id: researcher_1
                    role: Researcher
                    system_prompt: You research things.
                workflow:
                  name: workflow_b
                  entry: block1
                  transitions:
                    - from: block1
                      to: null
                blocks:
                  block1:
                    type: linear
                    soul_ref: researcher
                """)
            )

            _, _, workflows = discover_custom_assets(custom_dir)

            assert len(workflows) == 2
            assert "workflow_a" in workflows
            assert "workflow_b" in workflows


class TestDiscoverCustomAssets:
    """Integration tests for discover_custom_assets function."""

    @pytest.mark.xfail(
        reason="RUN-570 removed inline souls; RUN-571 will wire library discovery", strict=True
    )
    def test_discover_all_asset_types_together(self):
        """AC-1: Discover blocks, souls, and workflows all together."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir)

            # Create blocks directory with a block
            blocks_dir = custom_dir / "blocks"
            blocks_dir.mkdir()
            (blocks_dir / "test_block.py").write_text(
                dedent("""
                from runsight_core.blocks.base import BaseBlock
                from runsight_core.state import WorkflowState

                class TestBlock(BaseBlock):
                    async def execute(self, state: WorkflowState) -> WorkflowState:
                        return state
                """)
            )

            # Create souls directory with a soul
            souls_dir = custom_dir / "souls"
            souls_dir.mkdir()
            (souls_dir / "test_soul.yaml").write_text(
                dedent("""
                id: test_soul_1
                role: Test Role
                system_prompt: Test prompt
                """)
            )

            # Create workflows directory with a workflow
            workflows_dir = custom_dir / "workflows"
            workflows_dir.mkdir()
            (workflows_dir / "test_workflow.yaml").write_text(
                dedent("""
                version: "1.0"
                souls:
                  researcher:
                    id: researcher_1
                    role: Researcher
                    system_prompt: You research things.
                workflow:
                  name: test_workflow
                  entry: block1
                  transitions:
                    - from: block1
                      to: null
                blocks:
                  block1:
                    type: linear
                    soul_ref: researcher
                """)
            )

            blocks, souls, workflows = discover_custom_assets(custom_dir)

            assert len(blocks) == 1
            assert len(souls) == 1
            assert len(workflows) == 1
            assert "test_block" in blocks
            assert "test_soul" in souls
            assert "test_workflow" in workflows

    def test_missing_custom_dir_returns_empty_maps(self):
        """AC-2: Missing custom_dir returns empty dicts without raising exception."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir) / "nonexistent"

            blocks, souls, workflows = discover_custom_assets(custom_dir)

            assert blocks == {}
            assert souls == {}
            assert workflows == {}

    def test_partial_directory_structure(self):
        """AC-3: Only existing subdirectories are populated in result dicts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir)

            # Create only blocks and souls, not workflows
            blocks_dir = custom_dir / "blocks"
            blocks_dir.mkdir()
            (blocks_dir / "test.py").write_text(
                dedent("""
                from runsight_core.blocks.base import BaseBlock
                from runsight_core.state import WorkflowState

                class TestBlock(BaseBlock):
                    async def execute(self, state: WorkflowState) -> WorkflowState:
                        return state
                """)
            )

            souls_dir = custom_dir / "souls"
            souls_dir.mkdir()
            (souls_dir / "test.yaml").write_text(
                dedent("""
                id: test_1
                role: Test
                system_prompt: Test
                """)
            )

            blocks, souls, workflows = discover_custom_assets(custom_dir)

            assert len(blocks) == 1
            assert len(souls) == 1
            assert workflows == {}  # No workflows directory


class TestDiscoverCustomTools:
    """RUN-578: discovery of canonical custom tool files under custom/tools/."""

    @staticmethod
    def _load_symbols():
        import runsight_core.yaml.discovery as discovery_module

        discover_custom_tools = getattr(discovery_module, "discover_custom_tools", None)
        tool_meta = getattr(discovery_module, "ToolMeta", None)
        return discover_custom_tools, tool_meta

    def test_missing_custom_tools_directory_returns_empty_dict(self):
        discover_custom_tools, _ = self._load_symbols()
        assert callable(discover_custom_tools), (
            "Expected runsight_core.yaml.discovery.discover_custom_tools to exist"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = discover_custom_tools(Path(tmpdir))
            assert result == {}

    def test_discovers_python_and_request_executor_tool_files_by_filename_stem(self):
        discover_custom_tools, tool_meta = self._load_symbols()
        assert callable(discover_custom_tools), (
            "Expected runsight_core.yaml.discovery.discover_custom_tools to exist"
        )
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

            discovered = discover_custom_tools(base_dir)

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
        discover_custom_tools, _ = self._load_symbols()
        assert callable(discover_custom_tools), (
            "Expected runsight_core.yaml.discovery.discover_custom_tools to exist"
        )

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
                discover_custom_tools(base_dir)

    def test_malformed_yaml_raises_file_specific_error(self):
        discover_custom_tools, _ = self._load_symbols()
        assert callable(discover_custom_tools), (
            "Expected runsight_core.yaml.discovery.discover_custom_tools to exist"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            tools_dir = base_dir / "custom" / "tools"
            tools_dir.mkdir(parents=True)
            invalid_file = tools_dir / "broken.yaml"
            invalid_file.write_text(
                'version: "1.0"\ntype: custom\nexecutor: python\ncode: [not: valid'
            )

            with pytest.raises(Exception, match="broken.yaml"):
                discover_custom_tools(base_dir)

    def test_invalid_metadata_raises_file_specific_error(self):
        discover_custom_tools, _ = self._load_symbols()
        assert callable(discover_custom_tools), (
            "Expected runsight_core.yaml.discovery.discover_custom_tools to exist"
        )

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
                discover_custom_tools(base_dir)

    def test_custom_tool_rejects_both_code_and_code_file(self):
        discover_custom_tools, _ = self._load_symbols()
        assert callable(discover_custom_tools), (
            "Expected runsight_core.yaml.discovery.discover_custom_tools to exist"
        )

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
                discover_custom_tools(base_dir)

    def test_custom_tool_rejects_missing_code_file(self):
        discover_custom_tools, _ = self._load_symbols()
        assert callable(discover_custom_tools), (
            "Expected runsight_core.yaml.discovery.discover_custom_tools to exist"
        )

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
                discover_custom_tools(base_dir)

    def test_custom_tool_rejects_unreadable_code_file(self):
        discover_custom_tools, _ = self._load_symbols()
        assert callable(discover_custom_tools), (
            "Expected runsight_core.yaml.discovery.discover_custom_tools to exist"
        )

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
                discover_custom_tools(base_dir)

    def test_custom_tool_rejects_invalid_main_signature(self):
        discover_custom_tools, _ = self._load_symbols()
        assert callable(discover_custom_tools), (
            "Expected runsight_core.yaml.discovery.discover_custom_tools to exist"
        )

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
                discover_custom_tools(base_dir)

    def test_request_executor_requires_request_url(self):
        discover_custom_tools, _ = self._load_symbols()
        assert callable(discover_custom_tools), (
            "Expected runsight_core.yaml.discovery.discover_custom_tools to exist"
        )

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
                discover_custom_tools(base_dir)

    def test_request_executor_rejects_python_fields(self):
        discover_custom_tools, _ = self._load_symbols()
        assert callable(discover_custom_tools), (
            "Expected runsight_core.yaml.discovery.discover_custom_tools to exist"
        )

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
                discover_custom_tools(base_dir)

    def test_python_executor_rejects_request_fields(self):
        discover_custom_tools, _ = self._load_symbols()
        assert callable(discover_custom_tools), (
            "Expected runsight_core.yaml.discovery.discover_custom_tools to exist"
        )

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
                discover_custom_tools(base_dir)

    def test_unknown_executor_raises_file_specific_error(self):
        discover_custom_tools, _ = self._load_symbols()
        assert callable(discover_custom_tools), (
            "Expected runsight_core.yaml.discovery.discover_custom_tools to exist"
        )

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
                discover_custom_tools(base_dir)

    def test_duplicate_filename_derived_tool_id_raises_explicit_error(self, monkeypatch):
        discover_custom_tools, _ = self._load_symbols()
        assert callable(discover_custom_tools), (
            "Expected runsight_core.yaml.discovery.discover_custom_tools to exist"
        )

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
                discover_custom_tools(base_dir)

    @pytest.mark.parametrize("reserved_tool_id", ["http", "file_io", "delegate"])
    def test_reserved_builtin_tool_ids_are_rejected_during_discovery(self, reserved_tool_id):
        discover_custom_tools, _ = self._load_symbols()
        assert callable(discover_custom_tools), (
            "Expected runsight_core.yaml.discovery.discover_custom_tools to exist"
        )

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
                discover_custom_tools(base_dir)


class TestRepoPolicyForCustomTools:
    """RUN-525: repository policy should explicitly allow custom/tools assets."""

    def test_agents_policy_allows_custom_tools_directory(self):
        repo_policy = Path(__file__).resolve().parents[3] / "AGENTS.md"
        assert repo_policy.exists(), f"Expected repo policy at {repo_policy}"

        contents = repo_policy.read_text(encoding="utf-8")
        assert "custom/tools/" in contents or "- tools" in contents, (
            "AGENTS.md should explicitly allow custom/tools/ under the custom asset policy"
        )
