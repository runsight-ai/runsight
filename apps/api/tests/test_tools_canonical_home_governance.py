"""
Developer tooling canonical-home governance.

Owner: repo tooling and packages/shared codegen owners.
Boundary: contributor-facing docs and help text must point at tools/ for repo
tooling while preserving the supported package-local core schema generator path.
Exit criteria: delete this governance suite once tooling docs are generated from
the same manifest as package scripts and CI.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_README = REPO_ROOT / "tools" / "README.md"
SHARED_PACKAGE_JSON = REPO_ROOT / "packages" / "shared" / "package.json"
CORE_SCHEMA_SCRIPT = REPO_ROOT / "packages" / "core" / "scripts" / "generate_schema.py"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish.yml"


class TestToolingPathPreconditions:
    """Owner: packages/shared and CI owners. Exit: generated script manifest owns this."""

    def test_shared_package_uses_tools_for_supported_codegen_commands(self):
        package_json = json.loads(SHARED_PACKAGE_JSON.read_text(encoding="utf-8"))
        scripts = package_json["scripts"]

        assert scripts["generate:types"] == "bash ../../tools/generate-types.sh"
        assert scripts["check:types-fresh"] == "bash ../../tools/check-types-fresh.sh"

    def test_ci_keeps_the_supported_package_local_core_schema_command(self):
        text = CI_WORKFLOW.read_text(encoding="utf-8")

        assert "packages/core/scripts/generate_schema.py --check" in text


class TestContributorFacingToolingDocs:
    """Owner: repo tooling docs. Exit: docs generated from tooling manifest."""

    def test_tools_readme_does_not_claim_legacy_scripts_directory_is_still_current(self):
        text = TOOLS_README.read_text(encoding="utf-8")

        assert "Current legacy tooling still exists in `scripts/`." not in text, (
            "tools/README.md should describe tools/ as the canonical home instead of "
            "telling contributors that a repo-root scripts/ directory is still current."
        )

    def test_core_schema_generator_help_text_avoids_repo_root_scripts_examples(self):
        text = CORE_SCHEMA_SCRIPT.read_text(encoding="utf-8")

        assert "python scripts/generate_schema.py" not in text, (
            "packages/core/scripts/generate_schema.py still advertises the obsolete "
            "repo-root scripts/ command path."
        )
        assert "Run `python scripts/generate_schema.py` to regenerate." not in text, (
            "packages/core/scripts/generate_schema.py should not tell contributors to "
            "regenerate from a removed repo-root scripts/ location."
        )
        assert "packages/core/scripts/generate_schema.py" in text, (
            "packages/core/scripts/generate_schema.py should document its supported "
            "package-local command path for contributors."
        )
