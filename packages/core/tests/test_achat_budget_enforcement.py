"""
RUN-712 — Red tests: achat() budget enforcement via contextvars.

After achat() computes the response cost, it must:
1. Read _active_budget.get(None)
2. If session is not None: session.accrue(cost_usd=cost, tokens=total_tokens)
   then session.check_or_raise()
3. If session is None: no enforcement, response returned normally

Tests cover:
- _active_budget is read inside achat() after cost calculation
- When session is None, no enforcement occurs (zero overhead)
- When session is set, session.accrue() is called with cost and tokens
- session.check_or_raise() is called after accrual
- BudgetKilledException propagates out of achat()
- Cost from the triggering call IS included in accrued total
- Parent chain enforcement: block session within cap but parent flow session exceeds cap
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core.budget_enforcement import (
    BudgetKilledException,
    BudgetSession,
    _active_budget,
)
from runsight_core.llm.client import LiteLLMClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(
    content: str = "hello",
    cost: float = 0.002,
    prompt_tokens: int = 50,
    completion_tokens: int = 30,
    total_tokens: int = 80,
):
    """Build a mock litellm acompletion response."""
    message = MagicMock()
    message.content = content
    message.tool_calls = None

    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "stop"

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = total_tokens

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


# ---------------------------------------------------------------------------
# 1. No active budget — zero overhead
# ---------------------------------------------------------------------------


class TestAchatNoBudgetSession:
    """When _active_budget is None, achat() returns normally with no enforcement."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.002)
    async def test_no_session_returns_response_normally(self, mock_cost, mock_acompletion):
        """achat() must return the response dict when no budget session is active."""
        mock_acompletion.return_value = _make_response(content="hi there")

        token = _active_budget.set(None)
        try:
            client = LiteLLMClient(model_name="gpt-4o")
            result = await client.achat(messages=[{"role": "user", "content": "hello"}])

            assert result["content"] == "hi there"
            assert result["cost_usd"] == 0.002
        finally:
            _active_budget.reset(token)

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.002)
    async def test_no_session_does_not_raise(self, mock_cost, mock_acompletion):
        """achat() must not raise BudgetKilledException when no session is active."""
        mock_acompletion.return_value = _make_response()

        token = _active_budget.set(None)
        try:
            client = LiteLLMClient(model_name="gpt-4o")
            # Should complete without raising
            result = await client.achat(messages=[{"role": "user", "content": "hello"}])
            assert result is not None
        finally:
            _active_budget.reset(token)


# ---------------------------------------------------------------------------
# 2. Active budget session — accrue is called with correct values
# ---------------------------------------------------------------------------


class TestAchatAccruesIntoBudgetSession:
    """When _active_budget holds a BudgetSession, achat() must call
    session.accrue(cost_usd=..., tokens=...) with the response's cost and total_tokens."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.15)
    async def test_accrue_called_with_cost_and_tokens(self, mock_cost, mock_acompletion):
        """session.accrue() must receive cost_usd from completion_cost and
        tokens from response.usage.total_tokens."""
        mock_acompletion.return_value = _make_response(
            total_tokens=200, prompt_tokens=120, completion_tokens=80
        )

        session = BudgetSession(scope_name="block:test", cost_cap_usd=10.0)
        token = _active_budget.set(session)
        try:
            client = LiteLLMClient(model_name="gpt-4o")
            await client.achat(messages=[{"role": "user", "content": "hello"}])

            assert session.cost_usd == pytest.approx(0.15)
            assert session.tokens == 200
        finally:
            _active_budget.reset(token)

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.05)
    async def test_accrue_is_cumulative_across_calls(self, mock_cost, mock_acompletion):
        """Multiple achat() calls should accumulate cost and tokens in the session."""
        mock_acompletion.return_value = _make_response(total_tokens=100)

        session = BudgetSession(scope_name="block:multi", cost_cap_usd=10.0)
        token = _active_budget.set(session)
        try:
            client = LiteLLMClient(model_name="gpt-4o")
            await client.achat(messages=[{"role": "user", "content": "first"}])
            await client.achat(messages=[{"role": "user", "content": "second"}])

            assert session.cost_usd == pytest.approx(0.10)
            assert session.tokens == 200
        finally:
            _active_budget.reset(token)

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.30)
    async def test_triggering_call_cost_included_in_accrued_total(
        self, mock_cost, mock_acompletion
    ):
        """
        Acceptance scenario:
        Given session with cost_cap_usd=1.00, accumulated $0.80
        When achat() completes an LLM call costing $0.30
        Then session accrues to $1.10 (the triggering call IS included)
        """
        mock_acompletion.return_value = _make_response(total_tokens=500)

        session = BudgetSession(scope_name="block:trigger", cost_cap_usd=2.0)
        # Pre-accrue $0.80 before the call
        session.accrue(cost_usd=0.80, tokens=1000)

        token = _active_budget.set(session)
        try:
            client = LiteLLMClient(model_name="gpt-4o")
            try:
                await client.achat(messages=[{"role": "user", "content": "expensive"}])
            except BudgetKilledException:
                pass  # May or may not raise depending on cap

            # The key assertion: cost from the triggering call is included
            assert session.cost_usd == pytest.approx(1.10)
            assert session.tokens == 1500
        finally:
            _active_budget.reset(token)


# ---------------------------------------------------------------------------
# 3. check_or_raise() is called after accrual
# ---------------------------------------------------------------------------


class TestAchatCheckOrRaiseCalledAfterAccrual:
    """After accruing, achat() must call session.check_or_raise() which may raise."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.30)
    async def test_budget_killed_exception_propagates(self, mock_cost, mock_acompletion):
        """
        Acceptance scenario:
        Given session with cost_cap_usd=1.00, accumulated $0.80
        When achat() completes an LLM call costing $0.30
        Then session accrues to $1.10, check_or_raise() raises BudgetKilledException
        """
        mock_acompletion.return_value = _make_response(total_tokens=500)

        session = BudgetSession(
            scope_name="block:over-budget",
            cost_cap_usd=1.00,
            on_exceed="fail",
        )
        session.accrue(cost_usd=0.80, tokens=1000)

        token = _active_budget.set(session)
        try:
            client = LiteLLMClient(model_name="gpt-4o")
            with pytest.raises(BudgetKilledException) as exc_info:
                await client.achat(messages=[{"role": "user", "content": "over"}])

            assert exc_info.value.limit_kind == "cost_usd"
            assert exc_info.value.limit_value == 1.00
            assert exc_info.value.actual_value == pytest.approx(1.10)
        finally:
            _active_budget.reset(token)

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.10)
    async def test_under_budget_no_exception(self, mock_cost, mock_acompletion):
        """When accrual stays under cap, achat() returns normally."""
        mock_acompletion.return_value = _make_response(total_tokens=100)

        session = BudgetSession(
            scope_name="block:under-budget",
            cost_cap_usd=5.00,
            on_exceed="fail",
        )

        token = _active_budget.set(session)
        try:
            client = LiteLLMClient(model_name="gpt-4o")
            result = await client.achat(messages=[{"role": "user", "content": "safe"}])

            # Should return normally
            assert result["content"] == "hello"
            # And session should still have been accrued
            assert session.cost_usd == pytest.approx(0.10)
            assert session.tokens == 100
        finally:
            _active_budget.reset(token)

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.50)
    async def test_token_cap_exceeded_raises(self, mock_cost, mock_acompletion):
        """BudgetKilledException raised when token_cap is exceeded."""
        mock_acompletion.return_value = _make_response(total_tokens=6000)

        session = BudgetSession(
            scope_name="block:token-heavy",
            token_cap=5000,
            on_exceed="fail",
        )

        token = _active_budget.set(session)
        try:
            client = LiteLLMClient(model_name="gpt-4o")
            with pytest.raises(BudgetKilledException) as exc_info:
                await client.achat(messages=[{"role": "user", "content": "tokens"}])

            assert exc_info.value.limit_kind == "token_cap"
            assert exc_info.value.limit_value == 5000
            assert exc_info.value.actual_value == 6000
        finally:
            _active_budget.reset(token)

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=2.00)
    async def test_warn_mode_does_not_raise(self, mock_cost, mock_acompletion):
        """When on_exceed='warn', achat() should not raise even if cap is exceeded."""
        mock_acompletion.return_value = _make_response(total_tokens=500)

        session = BudgetSession(
            scope_name="block:warn-only",
            cost_cap_usd=1.00,
            on_exceed="warn",
        )

        token = _active_budget.set(session)
        try:
            client = LiteLLMClient(model_name="gpt-4o")
            result = await client.achat(messages=[{"role": "user", "content": "expensive"}])

            # Should return normally (no exception)
            assert result["content"] == "hello"
            # But cost should still be accrued
            assert session.cost_usd == pytest.approx(2.00)
        finally:
            _active_budget.reset(token)


# ---------------------------------------------------------------------------
# 4. Parent chain enforcement
# ---------------------------------------------------------------------------


class TestAchatParentChainEnforcement:
    """Parent chain enforcement: block session within cap but parent workflow
    session exceeds cap raises BudgetKilledException from parent."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.30)
    async def test_parent_exceeds_cap_raises_from_achat(self, mock_cost, mock_acompletion):
        """
        Acceptance scenario:
        Given block session within cap but parent flow session exceeds cap
        When achat() calls session.check_or_raise()
        Then BudgetKilledException(scope="workflow") raised from parent chain

        Setup: parent workflow cap=1.0, already at $0.80.
        Block has no cap of its own. achat() costs $0.30 => parent goes to $1.10.
        """
        mock_acompletion.return_value = _make_response(total_tokens=300)

        parent_session = BudgetSession(
            scope_name="workflow:main",
            cost_cap_usd=1.00,
            on_exceed="fail",
        )
        parent_session.accrue(cost_usd=0.80, tokens=2000)

        child_session = BudgetSession(
            scope_name="block:research",
            parent=parent_session,
        )

        token = _active_budget.set(child_session)
        try:
            client = LiteLLMClient(model_name="gpt-4o")
            with pytest.raises(BudgetKilledException) as exc_info:
                await client.achat(messages=[{"role": "user", "content": "research"}])

            # Exception comes from the workflow-level parent
            assert exc_info.value.scope == "workflow"
            assert exc_info.value.limit_kind == "cost_usd"
            assert exc_info.value.limit_value == 1.00
            assert exc_info.value.actual_value == pytest.approx(1.10)
        finally:
            _active_budget.reset(token)

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.10)
    async def test_parent_propagation_accrues_to_parent(self, mock_cost, mock_acompletion):
        """achat() accrues into child session which propagates to parent via accrue()."""
        mock_acompletion.return_value = _make_response(total_tokens=150)

        parent_session = BudgetSession(
            scope_name="workflow:main",
            cost_cap_usd=10.0,
        )
        child_session = BudgetSession(
            scope_name="block:step-1",
            parent=parent_session,
        )

        token = _active_budget.set(child_session)
        try:
            client = LiteLLMClient(model_name="gpt-4o")
            await client.achat(messages=[{"role": "user", "content": "step"}])

            # Child should have accrued
            assert child_session.cost_usd == pytest.approx(0.10)
            assert child_session.tokens == 150
            # Parent should also have accrued via propagation
            assert parent_session.cost_usd == pytest.approx(0.10)
            assert parent_session.tokens == 150
        finally:
            _active_budget.reset(token)


# ---------------------------------------------------------------------------
# 5. Response still returned when under budget
# ---------------------------------------------------------------------------


class TestAchatResponseIntegrityWithBudget:
    """When budget enforcement is active but within limits,
    the response dict must be complete and unmodified."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.002)
    async def test_response_keys_intact_with_active_budget(self, mock_cost, mock_acompletion):
        """All standard response keys must be present when budget session is active."""
        mock_acompletion.return_value = _make_response(
            content="the answer",
            prompt_tokens=50,
            completion_tokens=30,
            total_tokens=80,
        )

        session = BudgetSession(scope_name="block:check", cost_cap_usd=10.0)
        token = _active_budget.set(session)
        try:
            client = LiteLLMClient(model_name="gpt-4o")
            result = await client.achat(messages=[{"role": "user", "content": "hi"}])

            assert result["content"] == "the answer"
            assert result["cost_usd"] == 0.002
            assert result["prompt_tokens"] == 50
            assert result["completion_tokens"] == 30
            assert result["total_tokens"] == 80
            assert "finish_reason" in result
            assert "raw_message" in result
            assert "tool_calls" in result
        finally:
            _active_budget.reset(token)
