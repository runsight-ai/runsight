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


from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Soul
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.discovery import discover_custom_assets, _to_snake_case


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
        """AC-1: Empty souls directory returns empty dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir)
            souls_dir = custom_dir / "souls"
            souls_dir.mkdir()

            _, souls, _ = discover_custom_assets(custom_dir)
            assert souls == {}

    def test_discover_souls_nonexistent_directory(self):
        """AC-2: Nonexistent souls directory returns empty dict (no exception)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir)

            _, souls, _ = discover_custom_assets(custom_dir)
            assert souls == {}

    def test_discover_single_soul(self):
        """AC-3: Discover a single Soul from a YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir)
            souls_dir = custom_dir / "souls"
            souls_dir.mkdir()

            soul_file = souls_dir / "custom_soul.yaml"
            soul_file.write_text(
                dedent("""
                id: custom_soul_1
                role: Custom Researcher
                system_prompt: You are a custom researcher
                """)
            )

            _, souls, _ = discover_custom_assets(custom_dir)

            assert "custom_soul" in souls
            assert isinstance(souls["custom_soul"], Soul)
            assert souls["custom_soul"].id == "custom_soul_1"
            assert souls["custom_soul"].role == "Custom Researcher"

    def test_discover_multiple_souls(self):
        """AC-4: Discover multiple Souls from different YAML files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir)
            souls_dir = custom_dir / "souls"
            souls_dir.mkdir()

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

            _, souls, _ = discover_custom_assets(custom_dir)

            assert len(souls) == 2
            assert "soul_a" in souls
            assert "soul_b" in souls

    def test_discover_soul_with_tools(self):
        """AC-5: Discover Soul with optional tools field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir)
            souls_dir = custom_dir / "souls"
            souls_dir.mkdir()

            soul_file = souls_dir / "soul_with_tools.yaml"
            soul_file.write_text(
                dedent("""
                id: soul_with_tools_1
                role: Tool User
                system_prompt: You have tools
                tools:
                  - name: tool1
                    description: First tool
                """)
            )

            _, souls, _ = discover_custom_assets(custom_dir)

            assert "soul_with_tools" in souls
            assert souls["soul_with_tools"].tools is not None
            assert len(souls["soul_with_tools"].tools) == 1


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
