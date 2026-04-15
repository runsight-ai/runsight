"""
Failing tests for RUN-680: CodeBlock exit_handle on success path.

CodeBlock currently sets exit_handle="error" on failure but returns NO exit_handle
on the success path. When a CodeBlock lives inside a LoopBlock, it can never signal
success to trigger break_on_exit.

New behavior: if the returned JSON is a dict containing an "exit_handle" key (string
value), CodeBlock extracts it, pops it from the result, and passes it to BlockResult.

Tests cover:
- AC1: Code returns {"exit_handle": "done", "value": 42} -> exit_handle="done", output={"value": 42}
- AC2: Code returns {"value": 42} (no exit_handle key) -> exit_handle is None, output={"value": 42}
- AC3: Code returns a plain string -> exit_handle is None (no extraction attempted)
- AC4: CodeBlock inside LoopBlock with break_on_exit="pass" -> loop breaks when code returns "pass"
- AC5: Code fails (non-zero exit) -> exit_handle="error" (existing behavior, should PASS)
- Edge: {"exit_handle": 123} (non-string) -> ignore, exit_handle is None
- Edge: {"exit_handle": ""} (empty string) -> treat as None
- Edge: exit_handle key is popped from result before serialization
"""

import json
import textwrap

import pytest
from runsight_core import CodeBlock
from runsight_core.block_io import apply_block_output, build_block_context
from runsight_core.blocks.loop import LoopBlock
from runsight_core.state import BlockResult, WorkflowState


async def _exec(block, state, **extra_inputs):
    """Helper: build BlockContext, execute block, apply output to state."""
    ctx = build_block_context(block, state)
    if extra_inputs:
        ctx = ctx.model_copy(update={"inputs": {**ctx.inputs, **extra_inputs}})
    output = await block.execute(ctx)
    return apply_block_output(state, block.block_id, output)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides) -> WorkflowState:
    defaults = {
        "results": {},
        "metadata": {},
        "shared_memory": {},
        "execution_log": [],
    }
    defaults.update(overrides)
    return WorkflowState(**defaults)


# ---------------------------------------------------------------------------
# AC1: exit_handle extracted from dict result
# ---------------------------------------------------------------------------


class TestAC1ExitHandleExtracted:
    @pytest.mark.asyncio
    async def test_exit_handle_extracted_from_dict(self):
        """Code returning {"exit_handle": "done", "value": 42} should set
        BlockResult.exit_handle="done" and output={"value": 42} (handle stripped)."""
        code = textwrap.dedent("""\
def main(data):
    return {"exit_handle": "done", "value": 42}
""")
        block = CodeBlock("cb_ac1", code)
        state = _make_state()
        result = await _exec(block, state)

        br = result.results["cb_ac1"]
        assert isinstance(br, BlockResult)
        assert br.exit_handle == "done"
        parsed = json.loads(br.output)
        assert parsed == {"value": 42}
        assert "exit_handle" not in parsed


# ---------------------------------------------------------------------------
# AC2: no exit_handle key -> exit_handle is None
# ---------------------------------------------------------------------------


class TestAC2NoExitHandleKey:
    @pytest.mark.asyncio
    async def test_no_exit_handle_key_returns_none(self):
        """Code returning {"value": 42} (no exit_handle) should have
        BlockResult.exit_handle == None."""
        code = textwrap.dedent("""\
def main(data):
    return {"value": 42}
""")
        block = CodeBlock("cb_ac2", code)
        state = _make_state()
        result = await _exec(block, state)

        br = result.results["cb_ac2"]
        assert isinstance(br, BlockResult)
        assert br.exit_handle is None
        parsed = json.loads(br.output)
        assert parsed == {"value": 42}


# ---------------------------------------------------------------------------
# AC3: plain string return -> exit_handle is None
# ---------------------------------------------------------------------------


class TestAC3PlainStringReturn:
    @pytest.mark.asyncio
    async def test_plain_string_no_extraction(self):
        """Code returning a plain string should not attempt exit_handle
        extraction; BlockResult.exit_handle should be None."""
        code = textwrap.dedent("""\
def main(data):
    return "just a plain string"
""")
        block = CodeBlock("cb_ac3", code)
        state = _make_state()
        result = await _exec(block, state)

        br = result.results["cb_ac3"]
        assert isinstance(br, BlockResult)
        assert br.exit_handle is None
        assert br.output == "just a plain string"


# ---------------------------------------------------------------------------
# AC4: CodeBlock + LoopBlock integration — break_on_exit
# ---------------------------------------------------------------------------


class TestAC4LoopBlockBreakOnExit:
    @pytest.mark.asyncio
    async def test_loop_breaks_on_codeblock_exit_handle(self):
        """A CodeBlock returning {"exit_handle": "pass"} inside a LoopBlock with
        break_on_exit="pass" should cause the loop to break on that round.

        The CodeBlock reads the LoopBlock's round counter (loop_main_round) from
        shared_memory to decide when to emit exit_handle="pass"."""
        code = textwrap.dedent("""\
def main(data):
    round_num = data["shared_memory"].get("loop_main_round", 1)
    result = {"round": round_num}
    if round_num >= 2:
        result["exit_handle"] = "pass"
    return result
""")
        code_block = CodeBlock("code_inner", code)

        loop_block = LoopBlock(
            "loop_main",
            inner_block_refs=["code_inner"],
            max_rounds=5,
            break_on_exit="pass",
        )

        state = _make_state()
        result = await _exec(loop_block, state, blocks={"code_inner": code_block})

        # Loop should have broken early on round 2
        loop_meta = result.shared_memory.get("__loop__loop_main")
        assert loop_meta is not None
        assert loop_meta["broke_early"] is True
        assert loop_meta["rounds_completed"] == 2
        assert "exit_handle" in loop_meta.get("break_reason", "")

        # The code_inner result should have exit_handle="pass"
        inner_br = result.results.get("code_inner")
        assert isinstance(inner_br, BlockResult)
        assert inner_br.exit_handle == "pass"


# ---------------------------------------------------------------------------
# AC5: failure path — exit_handle="error" (existing behavior, should PASS)
# ---------------------------------------------------------------------------


class TestAC5FailurePathUnchanged:
    @pytest.mark.asyncio
    async def test_error_exit_handle_on_failure(self):
        """Code that raises an exception should produce
        BlockResult.exit_handle == 'error'. This is existing behavior."""
        code = textwrap.dedent("""\
def main(data):
    raise RuntimeError("intentional failure")
""")
        block = CodeBlock("cb_ac5", code)
        state = _make_state()
        result = await _exec(block, state)

        br = result.results["cb_ac5"]
        assert isinstance(br, BlockResult)
        assert br.exit_handle == "error"
        assert "Error:" in br.output


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_non_string_exit_handle_ignored(self):
        """If exit_handle value is not a string (e.g. integer), it should be
        ignored — exit_handle stays None and the key remains in output."""
        code = textwrap.dedent("""\
def main(data):
    return {"exit_handle": 123, "value": "ok"}
""")
        block = CodeBlock("cb_edge_int", code)
        state = _make_state()
        result = await _exec(block, state)

        br = result.results["cb_edge_int"]
        assert isinstance(br, BlockResult)
        assert br.exit_handle is None
        # Non-string exit_handle is NOT popped — stays in output
        parsed = json.loads(br.output)
        assert parsed["exit_handle"] == 123
        assert parsed["value"] == "ok"

    @pytest.mark.asyncio
    async def test_empty_string_exit_handle_treated_as_none(self):
        """If exit_handle value is an empty string, treat as None.
        The key should still be popped from the result."""
        code = textwrap.dedent("""\
def main(data):
    return {"exit_handle": "", "value": "ok"}
""")
        block = CodeBlock("cb_edge_empty", code)
        state = _make_state()
        result = await _exec(block, state)

        br = result.results["cb_edge_empty"]
        assert isinstance(br, BlockResult)
        assert br.exit_handle is None
        # Empty string exit_handle is popped from output
        parsed = json.loads(br.output)
        assert "exit_handle" not in parsed
        assert parsed["value"] == "ok"

    @pytest.mark.asyncio
    async def test_exit_handle_popped_from_serialized_output(self):
        """The exit_handle key should be removed from the serialized output
        when it is a valid string value."""
        code = textwrap.dedent("""\
def main(data):
    return {"exit_handle": "success", "a": 1, "b": 2}
""")
        block = CodeBlock("cb_edge_pop", code)
        state = _make_state()
        result = await _exec(block, state)

        br = result.results["cb_edge_pop"]
        assert isinstance(br, BlockResult)
        assert br.exit_handle == "success"
        parsed = json.loads(br.output)
        assert "exit_handle" not in parsed
        assert parsed == {"a": 1, "b": 2}

    @pytest.mark.asyncio
    async def test_only_exit_handle_key_produces_empty_dict(self):
        """If the dict only contains exit_handle and nothing else,
        output should be an empty dict."""
        code = textwrap.dedent("""\
def main(data):
    return {"exit_handle": "done"}
""")
        block = CodeBlock("cb_edge_only", code)
        state = _make_state()
        result = await _exec(block, state)

        br = result.results["cb_edge_only"]
        assert isinstance(br, BlockResult)
        assert br.exit_handle == "done"
        parsed = json.loads(br.output)
        assert parsed == {}
