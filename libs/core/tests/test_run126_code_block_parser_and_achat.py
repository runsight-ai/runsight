"""
RUN-126 — Red tests: CodeBlock parser registration + achat token breakdown.

These tests cover:
1. Parser: BLOCK_TYPE_REGISTRY includes "code" type
2. Parser: parse_workflow_yaml handles type: code → CodeBlock instance
3. Parser: CodeBlock with custom timeout_seconds and allowed_imports via YAML
4. Parser: CodeBlock with no `code` field → schema validation error
5. Parser: Direct builder test via BLOCK_TYPE_REGISTRY["code"] with mock BlockDef
6. achat: returns prompt_tokens, completion_tokens alongside total_tokens
7. achat: response.usage is None → defaults to 0 for all token fields
8. achat: response.usage exists but prompt_tokens/completion_tokens are None → default to 0
9. achat: backward-compat — callers using only content, cost_usd, total_tokens still work
"""

import pytest
from unittest.mock import MagicMock, patch
from pydantic import ValidationError

from runsight_core.yaml.parser import (
    parse_workflow_yaml,
    BLOCK_TYPE_REGISTRY,
)
from runsight_core.blocks.implementations import CodeBlock
from runsight_core.workflow import Workflow
from runsight_core.llm.client import LiteLLMClient
from runsight_core.yaml.schema import BlockDef


# ---------------------------------------------------------------------------
# 1. BLOCK_TYPE_REGISTRY includes "code"
# ---------------------------------------------------------------------------


class TestCodeBlockRegistration:
    def test_code_type_in_block_registry(self):
        """BLOCK_TYPE_REGISTRY must contain a 'code' builder."""
        assert "code" in BLOCK_TYPE_REGISTRY

    def test_code_builder_is_callable(self):
        """The 'code' builder must be callable."""
        assert callable(BLOCK_TYPE_REGISTRY["code"])


# ---------------------------------------------------------------------------
# 2. parse_workflow_yaml with type: code → CodeBlock
# ---------------------------------------------------------------------------

VALID_CODE_YAML = """\
version: "1.0"
config:
  model_name: gpt-4o
blocks:
  transform:
    type: code
    code: |
      def main(data):
          return {"out": 1}
workflow:
  name: test_code
  entry: transform
  transitions:
    - from: transform
      to: null
"""


class TestCodeBlockParsing:
    def test_parse_code_block_returns_workflow(self):
        """parse_workflow_yaml with type: code must return a valid Workflow."""
        wf = parse_workflow_yaml(VALID_CODE_YAML)
        assert isinstance(wf, Workflow)
        assert wf.name == "test_code"

    def test_parsed_code_block_is_codeblock_instance(self):
        """The block built by the parser must be a CodeBlock instance."""
        wf = parse_workflow_yaml(VALID_CODE_YAML)
        # Workflow stores blocks keyed by block_id
        block = wf.blocks.get("transform")
        assert block is not None
        assert isinstance(block, CodeBlock)

    def test_parsed_code_block_has_code(self):
        """The parsed CodeBlock must carry the code source from YAML."""
        wf = parse_workflow_yaml(VALID_CODE_YAML)
        block = wf.blocks["transform"]
        assert hasattr(block, "code")
        assert "def main(data)" in block.code


# ---------------------------------------------------------------------------
# 3. CodeBlock with custom timeout and allowed_imports via YAML
# ---------------------------------------------------------------------------

CODE_YAML_CUSTOM_OPTS = """\
version: "1.0"
config:
  model_name: gpt-4o
blocks:
  compute:
    type: code
    code: |
      import math
      def main(data):
          return {"pi": math.pi}
    timeout_seconds: 10
    allowed_imports:
      - math
workflow:
  name: test_code_opts
  entry: compute
  transitions:
    - from: compute
      to: null
"""


class TestCodeBlockParsingOptions:
    def test_custom_timeout_seconds(self):
        """Parser must pass timeout_seconds from YAML to CodeBlock."""
        wf = parse_workflow_yaml(CODE_YAML_CUSTOM_OPTS)
        block = wf.blocks["compute"]
        assert isinstance(block, CodeBlock)
        assert block.timeout_seconds == 10

    def test_custom_allowed_imports(self):
        """Parser must pass allowed_imports from YAML to CodeBlock."""
        wf = parse_workflow_yaml(CODE_YAML_CUSTOM_OPTS)
        block = wf.blocks["compute"]
        assert isinstance(block, CodeBlock)
        assert block.allowed_imports == ["math"]


# ---------------------------------------------------------------------------
# 4. CodeBlock with missing `code` field → Pydantic ValidationError
# ---------------------------------------------------------------------------

CODE_YAML_MISSING_CODE = """\
version: "1.0"
blocks:
  bad_block:
    type: code
workflow:
  name: test_bad_code
  entry: bad_block
  transitions:
    - from: bad_block
      to: null
"""


class TestCodeBlockSchemaValidation:
    def test_missing_code_field_raises_validation_error(self):
        """type: code without a `code` field must fail at Pydantic schema level."""
        with pytest.raises((ValidationError, ValueError), match=r"(?i)code"):
            parse_workflow_yaml(CODE_YAML_MISSING_CODE)


# ---------------------------------------------------------------------------
# 5. Direct builder test: BLOCK_TYPE_REGISTRY["code"] with mock BlockDef
# ---------------------------------------------------------------------------


class TestCodeBlockDirectBuilder:
    def test_builder_returns_codeblock_instance(self):
        """Calling BLOCK_TYPE_REGISTRY['code'] with a mock BlockDef must return a CodeBlock."""
        block_def = MagicMock(spec=BlockDef)
        block_def.type = "code"
        block_def.code = "def main(data):\n    return {'x': 1}\n"
        block_def.timeout_seconds = 5
        block_def.allowed_imports = ["json"]

        builder = BLOCK_TYPE_REGISTRY["code"]
        result = builder("test_block", block_def, {}, MagicMock(), {})

        assert isinstance(result, CodeBlock)

    def test_builder_passes_code_field(self):
        """The builder must forward the code field from BlockDef to CodeBlock."""
        code_src = "def main(data):\n    return {}\n"
        block_def = MagicMock(spec=BlockDef)
        block_def.type = "code"
        block_def.code = code_src
        block_def.timeout_seconds = 30
        block_def.allowed_imports = []

        builder = BLOCK_TYPE_REGISTRY["code"]
        result = builder("cb_1", block_def, {}, MagicMock(), {})

        assert hasattr(result, "code")
        assert result.code == code_src


# ---------------------------------------------------------------------------
# 6. achat returns prompt_tokens + completion_tokens
# ---------------------------------------------------------------------------


class TestAchatTokenBreakdown:
    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion")
    @patch("runsight_core.llm.client.completion_cost", return_value=0.002)
    async def test_achat_returns_prompt_and_completion_tokens(self, mock_cost, mock_acompletion):
        """achat must return prompt_tokens, completion_tokens, total_tokens, cost_usd, content."""
        usage = MagicMock()
        usage.prompt_tokens = 50
        usage.completion_tokens = 30
        usage.total_tokens = 80

        choice = MagicMock()
        choice.message.content = "hello"

        response = MagicMock()
        response.choices = [choice]
        response.usage = usage
        mock_acompletion.return_value = response

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(messages=[{"role": "user", "content": "hi"}])

        assert result["content"] == "hello"
        assert result["prompt_tokens"] == 50
        assert result["completion_tokens"] == 30
        assert result["total_tokens"] == 80
        assert result["cost_usd"] == 0.002

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion")
    @patch("runsight_core.llm.client.completion_cost", return_value=0.0)
    async def test_achat_usage_none_defaults_to_zero(self, mock_cost, mock_acompletion):
        """When response.usage is None, all token fields default to 0."""
        choice = MagicMock()
        choice.message.content = "ok"

        response = MagicMock()
        response.choices = [choice]
        response.usage = None
        mock_acompletion.return_value = response

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(messages=[{"role": "user", "content": "hi"}])

        assert result["prompt_tokens"] == 0
        assert result["completion_tokens"] == 0
        assert result["total_tokens"] == 0

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion")
    @patch("runsight_core.llm.client.completion_cost", return_value=0.0)
    async def test_achat_usage_partial_none_defaults_to_zero(self, mock_cost, mock_acompletion):
        """When usage exists but prompt_tokens/completion_tokens are None, default to 0."""
        usage = MagicMock()
        usage.prompt_tokens = None
        usage.completion_tokens = None
        usage.total_tokens = 42

        choice = MagicMock()
        choice.message.content = "partial"

        response = MagicMock()
        response.choices = [choice]
        response.usage = usage
        mock_acompletion.return_value = response

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(messages=[{"role": "user", "content": "hi"}])

        assert result["prompt_tokens"] == 0
        assert result["completion_tokens"] == 0
        assert result["total_tokens"] == 42


# ---------------------------------------------------------------------------
# 9. achat backward-compat: callers using only content, cost_usd, total_tokens
# ---------------------------------------------------------------------------


class TestAchatBackwardCompat:
    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion")
    @patch("runsight_core.llm.client.completion_cost", return_value=0.005)
    async def test_achat_backward_compat_existing_keys(self, mock_cost, mock_acompletion):
        """Callers that only access content, cost_usd, total_tokens must still work.

        This verifies the DoD item: 'Backward-compatible: callers using only
        total_tokens still work.'
        """
        usage = MagicMock()
        usage.prompt_tokens = 100
        usage.completion_tokens = 50
        usage.total_tokens = 150

        choice = MagicMock()
        choice.message.content = "backward compat"

        response = MagicMock()
        response.choices = [choice]
        response.usage = usage
        mock_acompletion.return_value = response

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(messages=[{"role": "user", "content": "hi"}])

        # Only access the pre-existing keys — no prompt_tokens/completion_tokens
        assert "content" in result
        assert result["content"] == "backward compat"
        assert "cost_usd" in result
        assert result["cost_usd"] == 0.005
        assert "total_tokens" in result
        assert result["total_tokens"] == 150
