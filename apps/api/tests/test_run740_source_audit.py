"""Source audit for RUN-740: test_run706_api_e2e.py must be upgraded to replace
mocked secrets and provider discovery with real filesystem fixtures.

These tests FAIL on the current codebase because test_run706 still uses:
  - mock_secrets = Mock() / mock_secrets.resolve = Mock(...) (fake secrets)
  - patch.object(..., "list_all", ...) against the provider_repo (fake provider discovery)
  - No SecretsEnvLoader usage (real secrets resolution is absent)

The target state (per RUN-740 AC):
  1. Only LiteLLMClient.achat is mocked (matching the docstring claim)
  2. Provider discovery uses real filesystem (FileSystemProviderRepo.list_all not patched)
  3. Secrets resolution uses real SecretsEnvLoader (no Mock() secrets object)
  4. The docstring accurately says only LLM is mocked — and that is actually true
"""

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve target file
# ---------------------------------------------------------------------------

# This file lives at apps/api/tests/test_run740_source_audit.py
# repo root is 3 levels up: tests/ -> api/ -> apps/ -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]

TARGET_FILE = _REPO_ROOT / "apps" / "api" / "tests" / "test_run706_api_e2e.py"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_source() -> str:
    """Return the full text of the target file."""
    return TARGET_FILE.read_text(encoding="utf-8")


def _read_lines() -> list[tuple[int, str]]:
    """Return (1-based line number, raw line) pairs for the target file."""
    text = _read_source()
    return [(i + 1, line) for i, line in enumerate(text.splitlines())]


def _find_pattern(pattern: re.Pattern) -> list[tuple[int, str]]:
    """Return all (lineno, stripped_line) pairs matching *pattern* in the target file."""
    hits = []
    for lineno, line in _read_lines():
        if pattern.search(line):
            hits.append((lineno, line.strip()))
    return hits


# ---------------------------------------------------------------------------
# AC1 — mock_secrets = Mock() must not exist
# ---------------------------------------------------------------------------


class TestNoMockSecretsObject:
    """The file must not construct a mock secrets object.

    Current state: the fixture at line ~183 does:
        mock_secrets = Mock()
        mock_secrets.resolve = Mock(return_value="sk-fake-test-key-for-e2e")

    These tests FAIL today because those lines are still present.
    """

    def test_no_mock_secrets_variable_assignment(self):
        """``mock_secrets = Mock()`` must not appear — secrets should be real."""
        pattern = re.compile(r"\bmock_secrets\s*=\s*Mock\s*\(\s*\)")
        hits = _find_pattern(pattern)
        assert hits == [], (
            "test_run706_api_e2e.py must not assign mock_secrets = Mock().\n"
            "Secrets should be resolved via the real SecretsEnvLoader, not a Mock.\n"
            f"Found {len(hits)} occurrence(s):\n"
            + "\n".join(f"  line {ln}: {text}" for ln, text in hits)
        )

    def test_no_mock_secrets_resolve_assignment(self):
        """``mock_secrets.resolve = Mock(...)`` must not appear — resolve should be real."""
        pattern = re.compile(r"\bmock_secrets\.resolve\s*=\s*Mock\s*\(")
        hits = _find_pattern(pattern)
        assert hits == [], (
            "test_run706_api_e2e.py must not stub mock_secrets.resolve with Mock().\n"
            "The real SecretsEnvLoader.resolve must be used instead.\n"
            f"Found {len(hits)} occurrence(s):\n"
            + "\n".join(f"  line {ln}: {text}" for ln, text in hits)
        )

    def test_no_secrets_kwarg_receiving_mock(self):
        """``secrets=mock_secrets`` must not appear — secrets kwarg should receive a real loader."""
        pattern = re.compile(r"\bsecrets\s*=\s*mock_secrets\b")
        hits = _find_pattern(pattern)
        assert hits == [], (
            "test_run706_api_e2e.py must not pass mock_secrets as the secrets argument.\n"
            "Wire a real SecretsEnvLoader instance instead.\n"
            f"Found {len(hits)} occurrence(s):\n"
            + "\n".join(f"  line {ln}: {text}" for ln, text in hits)
        )


# ---------------------------------------------------------------------------
# AC2 — provider_repo.list_all must NOT be patched out
# ---------------------------------------------------------------------------


class TestNoProviderRepoListAllPatch:
    """Provider discovery must use the real filesystem — list_all must not be patched.

    Current state: every test in TestSuccessfulRunE2E and TestFailingRunE2E wraps
    its execution block with:
        patch.object(
            app_with_real_services.state.execution_service.provider_repo,
            "list_all",
            return_value=[mock_provider],
        )

    These tests FAIL today because those patch.object("list_all", ...) calls are still present.
    """

    def test_no_patch_object_list_all(self):
        """``patch.object(`` targeting ``"list_all"`` must not appear."""
        # Match: patch.object( on one line followed by "list_all" on a nearby line.
        # We check for "list_all" as an argument to patch.object by detecting any line
        # that passes the string literal "list_all" — the only use of that string in this
        # file is as the second argument to patch.object(..., "list_all", ...).
        pattern = re.compile(r"""["']list_all["']""")
        hits = _find_pattern(pattern)
        assert hits == [], (
            "test_run706_api_e2e.py must not patch provider_repo.list_all.\n"
            "Provider discovery must use real FileSystemProviderRepo against the temp filesystem.\n"
            f"Found {len(hits)} occurrence(s):\n"
            + "\n".join(f"  line {ln}: {text}" for ln, text in hits)
        )

    def test_no_mock_provider_object(self):
        """``mock_provider = Mock()`` must not appear — provider fixtures must be real YAML."""
        pattern = re.compile(r"\bmock_provider\s*=\s*Mock\s*\(\s*\)")
        hits = _find_pattern(pattern)
        assert hits == [], (
            "test_run706_api_e2e.py must not create a mock_provider = Mock().\n"
            "Provider data should come from a real provider YAML file on the temp filesystem,\n"
            "discovered by the real FileSystemProviderRepo.list_all.\n"
            f"Found {len(hits)} occurrence(s):\n"
            + "\n".join(f"  line {ln}: {text}" for ln, text in hits)
        )


# ---------------------------------------------------------------------------
# AC3 — SecretsEnvLoader must be imported and used
# ---------------------------------------------------------------------------


class TestUsesSecretsEnvLoader:
    """The file must import and use the real SecretsEnvLoader.

    Current state: SecretsEnvLoader is never imported or referenced in test_run706.
    The file uses a bare Mock() object for secrets instead.

    These tests FAIL today because SecretsEnvLoader is absent from the file.
    """

    def test_imports_secretsenvloader(self):
        """``SecretsEnvLoader`` must appear in the file (import or usage)."""
        pattern = re.compile(r"\bSecretsEnvLoader\b")
        hits = _find_pattern(pattern)
        assert hits, (
            "test_run706_api_e2e.py must import and use SecretsEnvLoader for real secrets "
            "resolution.\n"
            "Currently SecretsEnvLoader is not referenced anywhere in the file — "
            "secrets are faked via Mock()."
        )

    def test_secretsenvloader_instantiated(self):
        """``SecretsEnvLoader(`` must appear — the loader must be constructed, not just imported."""
        pattern = re.compile(r"\bSecretsEnvLoader\s*\(")
        hits = _find_pattern(pattern)
        assert hits, (
            "test_run706_api_e2e.py must instantiate SecretsEnvLoader(...) to resolve secrets "
            "from the real filesystem.\n"
            "Currently no SecretsEnvLoader(...) call is found — the real loader is never created."
        )


# ---------------------------------------------------------------------------
# AC4 — Docstring accuracy: only LLM is mocked, and that claim is now true
# ---------------------------------------------------------------------------


class TestDocstringAccuracy:
    """The docstring claims 'ONLY the LLM is mocked' — that must actually be true.

    Current state: the docstring at lines 1-14 states:
        'ONLY the LLM is mocked (LiteLLMClient.achat)'
    but the fixture also mocks secrets (mock_secrets = Mock()) and patches
    provider_repo.list_all — contradicting the documented contract.

    After the fix these tests should pass because:
      - No mock secrets object → only LLM truly mocked for secrets layer
      - No list_all patch → only LLM truly mocked for provider discovery layer
      - LiteLLMClient.achat is still mocked (required, no real API keys in CI)

    AC4 is largely enforced transitively by AC1–AC3 above; this class adds an
    explicit check that LiteLLMClient.achat IS still mocked (the one permitted mock).
    """

    def test_litellmclient_achat_is_still_mocked(self):
        """``LiteLLMClient.achat`` must still be patched — no real LLM calls allowed."""
        pattern = re.compile(r"LiteLLMClient\.achat")
        hits = _find_pattern(pattern)
        assert hits, (
            "test_run706_api_e2e.py must still mock LiteLLMClient.achat to prevent real "
            "LLM API calls in CI.\n"
            "No reference to LiteLLMClient.achat found — the LLM mock has been removed entirely."
        )

    def test_docstring_mentions_only_llm_is_mocked(self):
        """The module docstring must contain the 'ONLY the LLM is mocked' claim."""
        source = _read_source()
        assert "ONLY the LLM is mocked" in source, (
            "test_run706_api_e2e.py module docstring must state "
            "'ONLY the LLM is mocked (LiteLLMClient.achat)'.\n"
            "The docstring is either missing or no longer contains this accuracy claim."
        )
