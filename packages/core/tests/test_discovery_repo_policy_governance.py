"""Discovery repo policy governance.

Owner: packages/core discovery scanner test owners.
Boundary: AGENTS.md must keep custom/tools under the custom runtime asset
policy so package-local discovery tests can exercise tool assets without
depending on repo-root runtime state.
Exit criteria: delete this guard when the custom asset policy is enforced by a
broader repository layout governance suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.governance


def test_agents_policy_allows_custom_tools_directory() -> None:
    repo_policy = Path(__file__).resolve().parents[3] / "AGENTS.md"
    assert repo_policy.exists(), f"Expected repo policy at {repo_policy}"

    contents = repo_policy.read_text(encoding="utf-8")
    assert "custom/tools/" in contents or "- tools" in contents, (
        "AGENTS.md should explicitly allow custom/tools/ under the custom asset policy"
    )
