"""
Unit tests for GateBlock and FileWriterBlock implementations.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from runsight_core.blocks.implementations import GateBlock, FileWriterBlock
from runsight_core.primitives import Soul
from runsight_core.runner import RunsightTeamRunner, ExecutionResult
from runsight_core.state import BlockResult, WorkflowState


def _mock_runner(output: str, cost: float = 0.01, tokens: int = 100) -> RunsightTeamRunner:
    runner = MagicMock(spec=RunsightTeamRunner)
    runner.execute_task = AsyncMock(
        return_value=ExecutionResult(
            task_id="test", soul_id="test", output=output, cost_usd=cost, total_tokens=tokens
        )
    )
    return runner


def _make_soul(soul_id: str = "gate_soul") -> Soul:
    return Soul(id=soul_id, role="Gate", system_prompt="Evaluate quality")


# ===== TestGateBlock =====


class TestGateBlock:
    @pytest.mark.asyncio
    async def test_gate_pass(self):
        """eval_key exists, runner returns PASS, verify results[block_id]=PASS, metadata has pass."""
        block_id = "gate1"
        eval_key = "research_output"
        gate_soul = _make_soul()
        runner = _mock_runner("PASS", cost=0.02, tokens=50)

        block = GateBlock(
            block_id=block_id,
            gate_soul=gate_soul,
            eval_key=eval_key,
            runner=runner,
        )
        state = WorkflowState(
            results={eval_key: BlockResult(output="Some research content to evaluate")}
        )

        result_state = await block.execute(state)

        assert result_state.results[block_id].output == "PASS"
        assert result_state.metadata[f"{block_id}_decision"] == "pass"

    @pytest.mark.asyncio
    async def test_gate_fail_raises(self):
        """runner returns FAIL: bad quality, verify ValueError raised with feedback."""
        block_id = "gate2"
        eval_key = "draft_output"
        gate_soul = _make_soul()
        runner = _mock_runner("FAIL: bad quality", cost=0.01, tokens=20)

        block = GateBlock(
            block_id=block_id,
            gate_soul=gate_soul,
            eval_key=eval_key,
            runner=runner,
        )
        state = WorkflowState(results={eval_key: BlockResult(output="Draft content")})

        with pytest.raises(ValueError, match=r"GateBlock 'gate2' FAILED: bad quality"):
            await block.execute(state)

    @pytest.mark.asyncio
    async def test_gate_missing_eval_key(self):
        """eval_key not in results, verify ValueError."""
        block_id = "gate3"
        eval_key = "missing_key"
        gate_soul = _make_soul()
        runner = _mock_runner("PASS")

        block = GateBlock(
            block_id=block_id,
            gate_soul=gate_soul,
            eval_key=eval_key,
            runner=runner,
        )
        state = WorkflowState(results={"other_key": BlockResult(output="value")})

        with pytest.raises(ValueError, match=f"eval_key '{eval_key}' not found in state.results"):
            await block.execute(state)

    @pytest.mark.asyncio
    async def test_gate_extract_field_on_pass(self):
        """eval_key contains JSON list, extract_field=author, runner returns PASS, verify extracted content."""
        block_id = "gate4"
        eval_key = "structured_output"
        extract_field = "author"
        json_content = [{"author": "extracted_content", "reviewer": "review"}]
        gate_soul = _make_soul()
        runner = _mock_runner("PASS")

        block = GateBlock(
            block_id=block_id,
            gate_soul=gate_soul,
            eval_key=eval_key,
            runner=runner,
            extract_field=extract_field,
        )
        state = WorkflowState(results={eval_key: BlockResult(output=json.dumps(json_content))})

        result_state = await block.execute(state)

        assert result_state.results[block_id].output == "extracted_content"
        assert result_state.metadata[f"{block_id}_decision"] == "pass"

    @pytest.mark.asyncio
    async def test_gate_extract_field_invalid_json(self):
        """eval_key contains non-JSON, extract_field set, runner returns PASS, falls back to decision_line."""
        block_id = "gate5"
        eval_key = "raw_output"
        extract_field = "soul_a"
        gate_soul = _make_soul()
        runner = _mock_runner("PASS")

        block = GateBlock(
            block_id=block_id,
            gate_soul=gate_soul,
            eval_key=eval_key,
            runner=runner,
            extract_field=extract_field,
        )
        state = WorkflowState(results={eval_key: BlockResult(output="not valid json at all")})

        result_state = await block.execute(state)

        # Should fall back to decision_line (PASS) when JSON parse fails
        assert result_state.results[block_id].output == "PASS"
        assert result_state.metadata[f"{block_id}_decision"] == "pass"

    @pytest.mark.asyncio
    async def test_gate_cost_propagation(self):
        """Verify total_cost_usd and total_tokens updated on PASS."""
        block_id = "gate6"
        eval_key = "content"
        gate_soul = _make_soul()
        cost, tokens = 0.05, 200
        runner = _mock_runner("PASS", cost=cost, tokens=tokens)

        block = GateBlock(
            block_id=block_id,
            gate_soul=gate_soul,
            eval_key=eval_key,
            runner=runner,
        )
        state = WorkflowState(
            results={eval_key: BlockResult(output="Content")},
            total_cost_usd=1.0,
            total_tokens=500,
        )

        result_state = await block.execute(state)

        assert result_state.total_cost_usd == 1.0 + cost
        assert result_state.total_tokens == 500 + tokens


# ===== TestFileWriterBlock =====


class TestFileWriterBlock:
    @pytest.mark.asyncio
    async def test_write_file_creates_file(self):
        """content_key in results, verify file created with correct content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "output.txt")
            content_key = "report"
            content = "Hello, world!\nThis is the report content."
            block_id = "writer1"

            block = FileWriterBlock(
                block_id=block_id,
                output_path=output_path,
                content_key=content_key,
            )
            state = WorkflowState(results={content_key: BlockResult(output=content)})

            await block.execute(state)

            assert Path(output_path).exists()
            assert Path(output_path).read_text(encoding="utf-8") == content

    @pytest.mark.asyncio
    async def test_write_file_creates_parent_dirs(self):
        """output_path has nested dirs, verify they're created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "nested" / "subdir" / "file.txt")
            content_key = "data"
            content = "nested content"
            block_id = "writer2"

            block = FileWriterBlock(
                block_id=block_id,
                output_path=output_path,
                content_key=content_key,
            )
            state = WorkflowState(results={content_key: BlockResult(output=content)})

            await block.execute(state)

            assert Path(output_path).exists()
            assert Path(output_path).read_text(encoding="utf-8") == content

    @pytest.mark.asyncio
    async def test_write_file_missing_content_key(self):
        """content_key not in results, verify ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "out.txt")
            content_key = "missing_content"
            block_id = "writer3"

            block = FileWriterBlock(
                block_id=block_id,
                output_path=output_path,
                content_key=content_key,
            )
            state = WorkflowState(results={"other_key": BlockResult(output="value")})

            with pytest.raises(ValueError, match=f"content_key '{content_key}'"):
                await block.execute(state)

    @pytest.mark.asyncio
    async def test_write_file_result_message(self):
        """Verify results[block_id] contains char count and path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "result.txt")
            content_key = "text"
            content = "Exactly 20 chars here!!"
            block_id = "writer4"

            block = FileWriterBlock(
                block_id=block_id,
                output_path=output_path,
                content_key=content_key,
            )
            state = WorkflowState(results={content_key: BlockResult(output=content)})

            result_state = await block.execute(state)

            msg = result_state.results[block_id].output
            assert "Written" in msg
            assert "chars to" in msg
            assert str(len(content)) in msg
            assert output_path in msg
            assert msg == f"Written {len(content)} chars to {output_path}"

    @pytest.mark.asyncio
    async def test_write_file_no_cost_change(self):
        """Verify total_cost_usd unchanged (no LLM calls)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "out.txt")
            content_key = "data"
            content = "some content"
            block_id = "writer5"

            block = FileWriterBlock(
                block_id=block_id,
                output_path=output_path,
                content_key=content_key,
            )
            initial_cost = 2.5
            state = WorkflowState(
                results={content_key: BlockResult(output=content)},
                total_cost_usd=initial_cost,
                total_tokens=1000,
            )

            result_state = await block.execute(state)

            assert result_state.total_cost_usd == initial_cost
            assert result_state.total_tokens == 1000
