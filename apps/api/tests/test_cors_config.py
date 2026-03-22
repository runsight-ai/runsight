"""Red tests for RUN-245: Make CORS allow_origins configurable via settings.

main.py currently hardcodes allow_origins=["*"]. After implementation:
- Settings.cors_origins defaults to ["http://localhost:5173"]
- RUNSIGHT_CORS_ORIGINS env var overrides the default (comma-separated)
- create_app() reads origins from settings, not hardcoded

These tests should all FAIL until the implementation is written.
"""


# ---------------------------------------------------------------------------
# Tests — Settings.cors_origins field
# ---------------------------------------------------------------------------


class TestCorsOriginsSettingsField:
    """Settings must expose a cors_origins field with the correct default."""

    def test_settings_has_cors_origins_attribute(self):
        """Settings class must have a cors_origins field."""
        from runsight_api.core.config import Settings

        s = Settings()
        assert hasattr(s, "cors_origins"), "Settings must have a cors_origins attribute"

    def test_default_cors_origins_is_localhost_5173(self):
        """Default value must be ["http://localhost:5173"], not ["*"]."""
        from runsight_api.core.config import Settings

        s = Settings()
        assert s.cors_origins == ["http://localhost:5173"]

    def test_default_is_a_list(self):
        """cors_origins must be a list, not a string."""
        from runsight_api.core.config import Settings

        s = Settings()
        assert isinstance(s.cors_origins, list)


# ---------------------------------------------------------------------------
# Tests — env var override
# ---------------------------------------------------------------------------


class TestCorsOriginsEnvOverride:
    """RUNSIGHT_CORS_ORIGINS env var must override the default."""

    def test_env_var_single_origin(self, monkeypatch):
        """A single origin in the env var produces a one-element list."""
        monkeypatch.setenv("RUNSIGHT_CORS_ORIGINS", "https://app.runsight.dev")

        # Force re-creation of a fresh Settings instance
        from runsight_api.core.config import Settings

        s = Settings()
        assert s.cors_origins == ["https://app.runsight.dev"]

    def test_env_var_multiple_origins(self, monkeypatch):
        """Comma-separated origins produce a multi-element list."""
        monkeypatch.setenv(
            "RUNSIGHT_CORS_ORIGINS",
            "https://app.runsight.dev,https://staging.runsight.dev",
        )

        from runsight_api.core.config import Settings

        s = Settings()
        assert s.cors_origins == [
            "https://app.runsight.dev",
            "https://staging.runsight.dev",
        ]

    def test_env_var_wildcard(self, monkeypatch):
        """Setting the env var to '*' produces ['*'] (opt-in wide open)."""
        monkeypatch.setenv("RUNSIGHT_CORS_ORIGINS", "*")

        from runsight_api.core.config import Settings

        s = Settings()
        assert s.cors_origins == ["*"]

    def test_env_var_strips_whitespace(self, monkeypatch):
        """Whitespace around origins in the env var is stripped."""
        monkeypatch.setenv(
            "RUNSIGHT_CORS_ORIGINS",
            " https://a.com , https://b.com ",
        )

        from runsight_api.core.config import Settings

        s = Settings()
        assert s.cors_origins == ["https://a.com", "https://b.com"]


# ---------------------------------------------------------------------------
# Tests — create_app() wires settings into CORS middleware
# ---------------------------------------------------------------------------


class TestCreateAppUsesSettingsForCors:
    """create_app() must read origins from settings, not hardcode ['*']."""

    def test_cors_middleware_does_not_use_wildcard_by_default(self):
        """The default app must NOT have allow_origins=['*']."""
        from runsight_api.main import create_app

        app = create_app()

        # Walk the middleware stack to find CORSMiddleware
        cors_mw = None
        # In Starlette, middleware is nested: app.middleware_stack
        # We inspect the app's user_middleware list added via add_middleware
        for mw in app.user_middleware:
            if mw.cls.__name__ == "CORSMiddleware":
                cors_mw = mw
                break

        assert cors_mw is not None, "CORSMiddleware must be registered"
        allow_origins = cors_mw.kwargs.get(
            "allow_origins", cors_mw.args[0] if cors_mw.args else None
        )
        assert allow_origins != ["*"], (
            f"Default CORS origins must not be ['*'], got {allow_origins}"
        )

    def test_cors_middleware_uses_default_localhost_origin(self):
        """The default app must use ['http://localhost:5173'] for CORS."""
        from runsight_api.main import create_app

        app = create_app()

        cors_mw = None
        for mw in app.user_middleware:
            if mw.cls.__name__ == "CORSMiddleware":
                cors_mw = mw
                break

        assert cors_mw is not None, "CORSMiddleware must be registered"
        allow_origins = cors_mw.kwargs.get("allow_origins")
        assert allow_origins == ["http://localhost:5173"], (
            f"Default CORS origins must be ['http://localhost:5173'], got {allow_origins}"
        )
