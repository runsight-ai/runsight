"""Source audit for RUN-739: test_run705_assertions_fire_e2e.py must be upgraded
to use HTTP layer instead of calling ExecutionService._run_workflow directly.

These tests FAIL on the current codebase because test_run705 still uses:
  - svc._run_workflow(...) / ExecutionService._run_workflow (private method calls)
  - Mock() for run_repo, workflow_repo, provider_repo (repo-level mocks)
  - Direct DB session reads instead of HTTP API calls for result verification

The target pattern (already correct in test_run706_api_e2e.py) is:
  - httpx.AsyncClient + ASGITransport exercising real HTTP endpoints
  - Only LiteLLMClient.achat is mocked
  - Results are verified through the API (GET /api/runs/{id}/nodes or equivalent)

AC from ticket:
  1. Tests exercise the full HTTP → service → engine → DB path
  2. Only LiteLLMClient.achat is mocked
  3. Assertion evaluation results are verified through the API, not direct DB reads
"""

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve target file
# ---------------------------------------------------------------------------

# This file lives at apps/api/tests/test_run739_source_audit.py
# repo root is 3 levels up (tests/ -> api/ -> apps/ -> repo root)
_REPO_ROOT = Path(__file__).resolve().parents[3]

TARGET_FILE = _REPO_ROOT / "apps" / "api" / "tests" / "test_run705_assertions_fire_e2e.py"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_lines() -> list[tuple[int, str]]:
    """Return (1-based line number, stripped line) pairs for the target file."""
    text = TARGET_FILE.read_text(encoding="utf-8")
    return [(i + 1, line) for i, line in enumerate(text.splitlines())]


def _find_pattern(pattern: re.Pattern) -> list[tuple[int, str]]:
    """Return all (lineno, raw_line) pairs matching *pattern* in the target file."""
    hits = []
    for lineno, line in _read_lines():
        if pattern.search(line):
            hits.append((lineno, line.strip()))
    return hits


# ---------------------------------------------------------------------------
# AC1 — No direct _run_workflow calls
# ---------------------------------------------------------------------------


class TestNoDirectRunWorkflowCalls:
    """The file must not call ExecutionService._run_workflow directly.

    Current state: every test method calls ``await svc._run_workflow(...)``
    which bypasses the entire HTTP layer.

    These tests FAIL today because those calls are still present.
    """

    def test_no_svc_underscore_run_workflow(self):
        """No ``svc._run_workflow`` calls — private method should not be called directly."""
        pattern = re.compile(r"\bsvc\._run_workflow\b")
        hits = _find_pattern(pattern)
        assert hits == [], (
            f"test_run705_assertions_fire_e2e.py must not call svc._run_workflow directly.\n"
            f"Found {len(hits)} occurrence(s):\n"
            + "\n".join(f"  line {ln}: {text}" for ln, text in hits)
        )

    def test_no_executionservice_underscore_run_workflow(self):
        """No ``ExecutionService._run_workflow`` pattern — confirms no qualified call either."""
        pattern = re.compile(r"ExecutionService\._run_workflow\b")
        hits = _find_pattern(pattern)
        assert hits == [], (
            f"test_run705_assertions_fire_e2e.py must not reference ExecutionService._run_workflow.\n"
            f"Found {len(hits)} occurrence(s):\n"
            + "\n".join(f"  line {ln}: {text}" for ln, text in hits)
        )

    def test_no_bare_underscore_run_workflow_call(self):
        """No bare ``._run_workflow(`` pattern anywhere — covers any receiver name."""
        pattern = re.compile(r"\._run_workflow\s*\(")
        hits = _find_pattern(pattern)
        assert hits == [], (
            f"test_run705_assertions_fire_e2e.py must not contain any ._run_workflow() call.\n"
            f"Found {len(hits)} occurrence(s):\n"
            + "\n".join(f"  line {ln}: {text}" for ln, text in hits)
        )


# ---------------------------------------------------------------------------
# AC2 — Uses AsyncClient + ASGITransport (HTTP layer)
# ---------------------------------------------------------------------------


class TestUsesHttpLayer:
    """The file must import and use httpx.AsyncClient with ASGITransport.

    Current state: no AsyncClient or ASGITransport usage anywhere in the file.

    These tests FAIL today because those imports/usages are absent.
    """

    def test_imports_asyncclient(self):
        """File must import AsyncClient from httpx."""
        pattern = re.compile(r"\bAsyncClient\b")
        hits = _find_pattern(pattern)
        assert hits, (
            "test_run705_assertions_fire_e2e.py must import and use httpx.AsyncClient.\n"
            "Currently no AsyncClient reference found — the file skips the HTTP layer entirely."
        )

    def test_imports_asgitransport(self):
        """File must import ASGITransport from httpx."""
        pattern = re.compile(r"\bASGITransport\b")
        hits = _find_pattern(pattern)
        assert hits, (
            "test_run705_assertions_fire_e2e.py must use httpx.ASGITransport.\n"
            "Currently no ASGITransport reference found — real HTTP transport is missing."
        )

    def test_uses_asyncclient_as_context_manager(self):
        """File must open an AsyncClient context (``async with AsyncClient``)."""
        pattern = re.compile(r"async\s+with\s+AsyncClient\s*\(")
        hits = _find_pattern(pattern)
        assert hits, (
            "test_run705_assertions_fire_e2e.py must use AsyncClient as an async context manager.\n"
            "Pattern ``async with AsyncClient(...)`` not found — HTTP client is never opened."
        )


# ---------------------------------------------------------------------------
# AC2 (continued) — Test methods use HTTP calls, not direct service calls
# ---------------------------------------------------------------------------


class TestMethodsUseHttpCalls:
    """Test methods must call client.post / client.get, not service methods directly.

    Current state: tests call ``await svc._run_workflow(...)`` instead of
    ``await client.post('/api/runs', ...)`` + ``await client.get(...)``.

    These tests FAIL today because no client.post or client.get is present.
    """

    def test_has_client_post_call(self):
        """At least one ``client.post(`` call must be present (to trigger a run via HTTP)."""
        pattern = re.compile(r"\bclient\.post\s*\(")
        hits = _find_pattern(pattern)
        assert hits, (
            "test_run705_assertions_fire_e2e.py must use ``client.post(...)`` to trigger runs "
            "through the HTTP layer.\n"
            "Currently no client.post() call found — execution is invoked directly, bypassing HTTP."
        )

    def test_has_client_get_call(self):
        """At least one ``client.get(`` call must be present (to fetch results via HTTP)."""
        pattern = re.compile(r"\bclient\.get\s*\(")
        hits = _find_pattern(pattern)
        assert hits, (
            "test_run705_assertions_fire_e2e.py must use ``client.get(...)`` to verify assertion "
            "results through the HTTP API.\n"
            "Currently no client.get() call found — results are read directly from DB sessions."
        )


# ---------------------------------------------------------------------------
# AC3 — Only LiteLLMClient.achat is mocked (no repo-level Mocks)
# ---------------------------------------------------------------------------


class TestOnlyLlmClientIsMocked:
    """Only LiteLLMClient.achat should be mocked.  Repo objects must NOT be Mock().

    Current state: ExecutionService is instantiated with
        run_repo=Mock(), workflow_repo=Mock(), provider_repo=Mock()
    which means the entire repo layer is faked, preventing real DB/filesystem paths.

    These tests FAIL today because those Mock() assignments are still present.
    """

    def test_no_run_repo_mock_assignment(self):
        """``run_repo=Mock()`` must not appear — run_repo should be real."""
        pattern = re.compile(r"\brun_repo\s*=\s*Mock\s*\(\s*\)")
        hits = _find_pattern(pattern)
        assert hits == [], (
            f"test_run705_assertions_fire_e2e.py must not pass Mock() as run_repo.\n"
            f"Found {len(hits)} occurrence(s) — remove repo mocks and wire real repositories:\n"
            + "\n".join(f"  line {ln}: {text}" for ln, text in hits)
        )

    def test_no_workflow_repo_mock_assignment(self):
        """``workflow_repo=Mock()`` must not appear — workflow_repo should be real."""
        pattern = re.compile(r"\bworkflow_repo\s*=\s*Mock\s*\(\s*\)")
        hits = _find_pattern(pattern)
        assert hits == [], (
            f"test_run705_assertions_fire_e2e.py must not pass Mock() as workflow_repo.\n"
            f"Found {len(hits)} occurrence(s) — remove repo mocks and wire real repositories:\n"
            + "\n".join(f"  line {ln}: {text}" for ln, text in hits)
        )

    def test_no_provider_repo_mock_assignment(self):
        """``provider_repo=Mock()`` must not appear — provider_repo should be real."""
        pattern = re.compile(r"\bprovider_repo\s*=\s*Mock\s*\(\s*\)")
        hits = _find_pattern(pattern)
        assert hits == [], (
            f"test_run705_assertions_fire_e2e.py must not pass Mock() as provider_repo.\n"
            f"Found {len(hits)} occurrence(s) — remove repo mocks and wire real repositories:\n"
            + "\n".join(f"  line {ln}: {text}" for ln, text in hits)
        )

    def test_litellm_achat_is_mocked(self):
        """LiteLLMClient.achat must still be mocked (no real LLM calls allowed)."""
        pattern = re.compile(r"LiteLLMClient\.achat")
        hits = _find_pattern(pattern)
        assert hits, (
            "test_run705_assertions_fire_e2e.py must mock LiteLLMClient.achat to prevent "
            "real LLM API calls.\n"
            "Currently no LiteLLMClient.achat mock found."
        )


# ---------------------------------------------------------------------------
# AC3 (continued) — Results verified via API, not direct DB session reads
# ---------------------------------------------------------------------------


class TestResultsVerifiedViaApi:
    """Assertion evaluation results must come from the HTTP API, not direct DB reads.

    Current state: every test opens a ``Session(db_engine)`` and reads RunNode fields
    (eval_passed, eval_score, eval_results) directly from SQLite — bypassing the API
    contract that the ticket requires verifying.

    These tests FAIL today because the Session/RunNode DB read pattern is still present.
    """

    def test_no_direct_session_get_runnode(self):
        """``session.get(RunNode, ...)`` must not appear — use the HTTP API instead."""
        pattern = re.compile(r"\bsession\.get\s*\(\s*RunNode\b")
        hits = _find_pattern(pattern)
        assert hits == [], (
            f"test_run705_assertions_fire_e2e.py must not read RunNode from the DB directly.\n"
            f"Found {len(hits)} occurrence(s) — verify eval results through the HTTP API:\n"
            + "\n".join(f"  line {ln}: {text}" for ln, text in hits)
        )

    def test_no_direct_eval_passed_db_read(self):
        """``node.eval_passed`` must not be asserted directly — use API response fields."""
        pattern = re.compile(r"\bnode\.eval_passed\b")
        hits = _find_pattern(pattern)
        assert hits == [], (
            f"test_run705_assertions_fire_e2e.py must not access node.eval_passed from a DB "
            f"session directly.\n"
            f"Found {len(hits)} occurrence(s) — read eval_passed from the API JSON response:\n"
            + "\n".join(f"  line {ln}: {text}" for ln, text in hits)
        )

    def test_no_direct_eval_score_db_read(self):
        """``node.eval_score`` must not be asserted directly — use API response fields."""
        pattern = re.compile(r"\bnode\.eval_score\b")
        hits = _find_pattern(pattern)
        assert hits == [], (
            f"test_run705_assertions_fire_e2e.py must not access node.eval_score from a DB "
            f"session directly.\n"
            f"Found {len(hits)} occurrence(s) — read eval_score from the API JSON response:\n"
            + "\n".join(f"  line {ln}: {text}" for ln, text in hits)
        )

    def test_no_direct_eval_results_db_read(self):
        """``node.eval_results`` must not be asserted directly — use API response fields."""
        pattern = re.compile(r"\bnode\.eval_results\b")
        hits = _find_pattern(pattern)
        assert hits == [], (
            f"test_run705_assertions_fire_e2e.py must not access node.eval_results from a DB "
            f"session directly.\n"
            f"Found {len(hits)} occurrence(s) — read eval_results from the API JSON response:\n"
            + "\n".join(f"  line {ln}: {text}" for ln, text in hits)
        )
