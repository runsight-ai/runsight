"""Tests for prompt hash and soul version computation.

Tests target `compute_prompt_hash` and `compute_soul_version` utility functions
expected at `runsight_core.observer`.

Hash specification:
  - prompt_hash  = SHA-256 hex digest of soul.system_prompt
  - soul_version = SHA-256 hex digest of soul.model_dump_json()
  - When soul is None, both return None

"""

import hashlib

from runsight_core.primitives import Soul

# ---------------------------------------------------------------------------
# Hash function import helper
# ---------------------------------------------------------------------------


def _import_hash_functions():
    from runsight_core.observer import compute_prompt_hash, compute_soul_version

    return compute_prompt_hash, compute_soul_version


# ---------------------------------------------------------------------------
# 1. Import smoke tests
# ---------------------------------------------------------------------------


class TestImportHashFunctions:
    def test_compute_prompt_hash_importable(self):
        """compute_prompt_hash can be imported from runsight_core.observer."""
        compute_prompt_hash, _ = _import_hash_functions()
        assert callable(compute_prompt_hash)

    def test_compute_soul_version_importable(self):
        """compute_soul_version can be imported from runsight_core.observer."""
        _, compute_soul_version = _import_hash_functions()
        assert callable(compute_soul_version)


# ---------------------------------------------------------------------------
# 2. prompt_hash — SHA-256 of system_prompt
# ---------------------------------------------------------------------------


class TestPromptHash:
    def test_sha256_of_system_prompt(self):
        """prompt_hash equals SHA-256 hex digest of soul.system_prompt."""
        compute_prompt_hash, _ = _import_hash_functions()
        soul = Soul(
            id="prompt_hash_soul",
            kind="soul",
            name="Prompt Hash Analyst",
            role="Analyst",
            system_prompt="You are a helpful assistant.",
        )
        expected = hashlib.sha256("You are a helpful assistant.".encode()).hexdigest()
        assert compute_prompt_hash(soul) == expected

    def test_different_system_prompt_different_hash(self):
        """Changing system_prompt produces a different prompt_hash."""
        compute_prompt_hash, _ = _import_hash_functions()
        soul_a = Soul(
            id="prompt_variant_soul",
            kind="soul",
            name="Prompt Variant Analyst",
            role="Analyst",
            system_prompt="Summarize risk.",
        )
        soul_b = Soul(
            id="prompt_variant_soul",
            kind="soul",
            name="Prompt Variant Analyst",
            role="Analyst",
            system_prompt="Summarize opportunity.",
        )
        assert compute_prompt_hash(soul_a) != compute_prompt_hash(soul_b)

    def test_same_system_prompt_same_hash(self):
        """Same system_prompt (even with different id) produces identical prompt_hash."""
        compute_prompt_hash, _ = _import_hash_functions()
        soul_a = Soul(
            id="reviewer_alpha",
            kind="soul",
            name="Reviewer Alpha",
            role="Reviewer",
            system_prompt="Shared review prompt",
        )
        soul_b = Soul(
            id="reviewer_beta",
            kind="soul",
            name="Reviewer Beta",
            role="Auditor",
            system_prompt="Shared review prompt",
        )
        assert compute_prompt_hash(soul_a) == compute_prompt_hash(soul_b)

    def test_deterministic_across_calls(self):
        """Same soul produces the same prompt_hash across multiple calls."""
        compute_prompt_hash, _ = _import_hash_functions()
        soul = Soul(
            id="stable_prompt_soul",
            kind="soul",
            name="Stable Prompt Analyst",
            role="Analyst",
            system_prompt="Stable prompt",
        )
        h1 = compute_prompt_hash(soul)
        h2 = compute_prompt_hash(soul)
        assert h1 == h2

    def test_none_soul_returns_none(self):
        """compute_prompt_hash(None) returns None."""
        compute_prompt_hash, _ = _import_hash_functions()
        assert compute_prompt_hash(None) is None


# ---------------------------------------------------------------------------
# 3. soul_version — SHA-256 of full soul JSON
# ---------------------------------------------------------------------------


class TestSoulVersion:
    def test_sha256_of_full_soul_json(self):
        """soul_version equals SHA-256 hex digest of soul.model_dump_json()."""
        _, compute_soul_version = _import_hash_functions()
        soul = Soul(
            id="versioned_soul",
            kind="soul",
            name="Versioned Soul",
            role="Analyst",
            system_prompt="You are an analyst.",
            model_name="gpt-4o",
        )
        expected = hashlib.sha256(soul.model_dump_json().encode()).hexdigest()
        assert compute_soul_version(soul) == expected

    def test_changed_model_name_different_soul_version(self):
        """Changing model_name produces a different soul_version."""
        _, compute_soul_version = _import_hash_functions()
        soul_a = Soul(
            id="model_variant_soul",
            kind="soul",
            name="Model Variant Analyst",
            role="Analyst",
            system_prompt="Compare model outputs.",
            model_name="gpt-4o",
        )
        soul_b = Soul(
            id="model_variant_soul",
            kind="soul",
            name="Model Variant Analyst",
            role="Analyst",
            system_prompt="Compare model outputs.",
            model_name="claude-3",
        )
        assert compute_soul_version(soul_a) != compute_soul_version(soul_b)

    def test_changed_model_name_same_prompt_hash(self):
        """Changing model_name does NOT change prompt_hash (only system_prompt matters)."""
        compute_prompt_hash, compute_soul_version = _import_hash_functions()
        soul_a = Soul(
            id="model_prompt_soul",
            kind="soul",
            name="Model Prompt Analyst",
            role="Analyst",
            system_prompt="Keep the prompt stable.",
            model_name="gpt-4o",
        )
        soul_b = Soul(
            id="model_prompt_soul",
            kind="soul",
            name="Model Prompt Analyst",
            role="Analyst",
            system_prompt="Keep the prompt stable.",
            model_name="claude-3",
        )
        # prompt_hash stays the same
        assert compute_prompt_hash(soul_a) == compute_prompt_hash(soul_b)
        # but soul_version differs
        assert compute_soul_version(soul_a) != compute_soul_version(soul_b)

    def test_same_soul_same_version(self):
        """Identical souls produce the same soul_version."""
        _, compute_soul_version = _import_hash_functions()
        soul_a = Soul(
            id="stable_version_soul",
            kind="soul",
            name="Stable Version Analyst",
            role="Analyst",
            system_prompt="Keep the version stable.",
            model_name="gpt-4o",
        )
        soul_b = Soul(
            id="stable_version_soul",
            kind="soul",
            name="Stable Version Analyst",
            role="Analyst",
            system_prompt="Keep the version stable.",
            model_name="gpt-4o",
        )
        assert compute_soul_version(soul_a) == compute_soul_version(soul_b)

    def test_deterministic_across_calls(self):
        """Same soul produces the same soul_version across multiple calls."""
        _, compute_soul_version = _import_hash_functions()
        soul = Soul(
            id="deterministic_version_soul",
            kind="soul",
            name="Deterministic Version Analyst",
            role="Analyst",
            system_prompt="Keep the version deterministic.",
        )
        v1 = compute_soul_version(soul)
        v2 = compute_soul_version(soul)
        assert v1 == v2

    def test_none_soul_returns_none(self):
        """compute_soul_version(None) returns None."""
        _, compute_soul_version = _import_hash_functions()
        assert compute_soul_version(None) is None

    def test_changed_id_different_soul_version(self):
        """Changing soul id produces a different soul_version (full JSON includes id)."""
        _, compute_soul_version = _import_hash_functions()
        soul_a = Soul(
            id="version_candidate_alpha",
            kind="soul",
            name="Version Candidate Alpha",
            role="Analyst",
            system_prompt="Compare identity changes.",
        )
        soul_b = Soul(
            id="version_candidate_beta",
            kind="soul",
            name="Version Candidate Beta",
            role="Analyst",
            system_prompt="Compare identity changes.",
        )
        assert compute_soul_version(soul_a) != compute_soul_version(soul_b)
