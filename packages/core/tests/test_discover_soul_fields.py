"""Standalone soul discovery preserves declared Soul fields and defaults."""

from textwrap import dedent


class TestDiscoverSoulFieldPreservation:
    def test_discover_soul_preserves_extended_fields(self, tmp_path):
        base_dir = tmp_path
        souls_dir = base_dir / "custom" / "souls"
        souls_dir.mkdir(parents=True)

        (souls_dir / "extended_soul.yaml").write_text(
            dedent("""
            id: extended_soul
            kind: soul
            name: Extended Soul
            role: Extended Soul
            system_prompt: Preserve every field.
            tools:
              - profile_lookup
            max_tool_iterations: 9
            model_name: local-analysis-model
            provider: local_provider
            temperature: 0.6
            max_tokens: 8192
            avatar_color: "#224466"
            """)
        )

        from runsight_core.yaml.discovery import SoulScanner

        souls = SoulScanner(base_dir).scan().ids()
        soul = souls["extended_soul"]

        assert soul.kind == "soul"
        assert soul.name == "Extended Soul"
        assert soul.tools == ["profile_lookup"]
        assert soul.max_tool_iterations == 9
        assert soul.model_name == "local-analysis-model"
        assert soul.provider == "local_provider"
        assert soul.temperature == 0.6
        assert soul.max_tokens == 8192
        assert soul.avatar_color == "#224466"

    def test_discover_soul_missing_optional_fields_uses_defaults(self, tmp_path):
        base_dir = tmp_path
        souls_dir = base_dir / "custom" / "souls"
        souls_dir.mkdir(parents=True)

        (souls_dir / "minimal_soul.yaml").write_text(
            dedent("""
            id: minimal_soul
            kind: soul
            name: Minimal Soul
            role: Minimal Soul
            system_prompt: Keep defaults.
            """)
        )

        from runsight_core.yaml.discovery import SoulScanner

        souls = SoulScanner(base_dir).scan().ids()
        soul = souls["minimal_soul"]

        assert soul.kind == "soul"
        assert soul.name == "Minimal Soul"
        assert soul.max_tool_iterations == 5
        assert soul.model_name is None
        assert soul.provider is None
        assert soul.temperature is None
        assert soul.max_tokens is None
        assert soul.avatar_color is None

    def test_discover_soul_missing_required_fields_raises_file_specific_error(self, tmp_path):
        base_dir = tmp_path
        souls_dir = base_dir / "custom" / "souls"
        souls_dir.mkdir(parents=True)

        (souls_dir / "valid_soul.yaml").write_text(
            dedent("""
            id: valid_soul
            kind: soul
            name: Valid Soul
            role: Valid Soul
            system_prompt: Keep loading valid souls.
            """)
        )

        (souls_dir / "invalid_soul.yaml").write_text(
            dedent("""
            id: invalid_soul
            kind: soul
            name: Invalid Soul
            system_prompt: Missing a role.
            """)
        )

        from runsight_core.yaml.discovery import SoulScanner

        try:
            SoulScanner(base_dir).scan()
            raise AssertionError("SoulScanner.scan() should fail for invalid soul files")
        except ValueError as exc:
            message = str(exc)

        assert "invalid_soul.yaml" in message
        assert "role" in message

    def test_discover_soul_ignores_unknown_extra_keys(self, tmp_path):
        base_dir = tmp_path
        souls_dir = base_dir / "custom" / "souls"
        souls_dir.mkdir(parents=True)

        (souls_dir / "future_soul.yaml").write_text(
            dedent("""
            id: future_soul
            kind: soul
            name: Future Soul
            role: Future Soul
            system_prompt: Ignore unknown keys.
            provider: local_provider
            unknown_future_flag: true
            """)
        )

        from runsight_core.yaml.discovery import SoulScanner

        souls = SoulScanner(base_dir).scan().ids()
        soul = souls["future_soul"]

        assert soul.kind == "soul"
        assert soul.name == "Future Soul"
        assert soul.provider == "local_provider"

    def test_discover_empty_soul_yaml_is_skipped(self, tmp_path):
        base_dir = tmp_path
        souls_dir = base_dir / "custom" / "souls"
        souls_dir.mkdir(parents=True)

        (souls_dir / "empty_soul.yaml").write_text("", encoding="utf-8")
        (souls_dir / "loaded_soul.yaml").write_text(
            dedent("""
            id: loaded_soul
            kind: soul
            name: Loaded Soul
            role: Loaded Soul
            system_prompt: Still loads.
            """),
            encoding="utf-8",
        )

        from runsight_core.yaml.discovery import SoulScanner

        souls = SoulScanner(base_dir).scan().ids()

        assert "empty_soul" not in souls
        assert "loaded_soul" in souls
