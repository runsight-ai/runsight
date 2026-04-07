"""
RUN-688 — Red tests: Remove stale `assertions: null` from soul YAML files.

Soul-level assertions were retired when eval moved to block scope.
Four soul files still carry a vestigial `assertions: null` key that
must be removed.

AC:
  Given: all YAML files in custom/souls/
  When: searched for `assertions:` key
  Then: zero matches

DoD:
  - No `assertions:` key in any soul YAML file
"""

from __future__ import annotations

from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Repo root discovery (same pattern as test_run575_template_alignment.py)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # runsight/
CUSTOM_SOULS = REPO_ROOT / "custom" / "souls"

# ===========================================================================
# Preconditions
# ===========================================================================


class TestPreconditions:
    """Sanity checks so failures are diagnostic, not cryptic."""

    def test_custom_souls_directory_exists(self):
        """custom/souls/ must exist for the scan to be meaningful."""
        assert CUSTOM_SOULS.exists(), f"Directory not found: {CUSTOM_SOULS}"

    def test_at_least_one_soul_file_exists(self):
        """There should be at least one soul YAML file to scan."""
        files = sorted(CUSTOM_SOULS.glob("*.yaml"))
        assert len(files) > 0, "No YAML files found in custom/souls/"


# ===========================================================================
# AC: zero soul YAML files contain an `assertions` key
# ===========================================================================


class TestNoAssertionsKeyInSoulYaml:
    """Every soul YAML file must be free of the retired `assertions` key."""

    @staticmethod
    def _discover_soul_files() -> list[Path]:
        """Return all .yaml files under custom/souls/."""
        if not CUSTOM_SOULS.exists():
            return []
        return sorted(CUSTOM_SOULS.glob("*.yaml"))

    def test_no_soul_file_contains_assertions_key(self):
        """Scan all soul YAML files; none should have a top-level `assertions` key."""
        files = self._discover_soul_files()
        violations: list[str] = []

        for soul_file in files:
            try:
                data = yaml.safe_load(soul_file.read_text())
            except yaml.YAMLError:
                continue  # Unparseable files are not our concern

            if not isinstance(data, dict):
                continue

            if "assertions" in data:
                violations.append(soul_file.name)

        assert violations == [], (
            "Soul YAML files still contain a stale `assertions` key:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    # The four known-offender tests below were removed because the soul files
    # (workspace_operator, gate_evaluator, web_researcher, news_to_slack) were
    # deleted as part of the soul library cleanup.  The broad scan test above
    # (`test_no_soul_file_contains_assertions_key`) covers all remaining files.
