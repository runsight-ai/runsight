"""README documents workspace persistence requirements for package and Docker use."""

from tests.core.workspace_resolution_helpers import README


class TestReadmeGuidance:
    """User-facing docs must describe the Docker workspace-root persistence contract."""

    def test_readme_explains_mounting_workspace_root_for_db_and_settings_persistence(self):
        text = README.read_text(encoding="utf-8").lower()

        mentions_workspace_root = "workspace root" in text or "whole workspace" in text
        mentions_not_custom_only = "not only `custom/`" in text or "not just `custom/`" in text
        mentions_runtime_persistence = ".runsight/" in text and any(
            phrase in text for phrase in ("db", "settings", "persistence")
        )

        assert (
            mentions_workspace_root and mentions_not_custom_only and mentions_runtime_persistence
        ), (
            "README must explain that Docker users should mount the whole workspace root, not "
            "just custom/, when they want .runsight/ DB/settings persistence."
        )
