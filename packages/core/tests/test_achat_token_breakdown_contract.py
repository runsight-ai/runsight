"""
CodeBlock parser registration and achat token breakdown behavior.

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

from unittest.mock import MagicMock, patch

import pytest
from runsight_core.llm.client import LiteLLMClient

# ---------------------------------------------------------------------------
# 1. BLOCK_TYPE_REGISTRY includes "code"
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

        This preserves the response shape used by callers that only read
        total_tokens.
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
