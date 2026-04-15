"""Red tests for RUN-861: CORS default port mismatch.

config.py currently defaults cors_origins to http://localhost:5173.
Vite runs on port 3000. After the fix, the default must be http://localhost:3000.

This test should FAIL until the green implementation is written.
"""


class TestCorsDefaultMatchesVitePort:
    """Settings.cors_origins default must match the actual Vite dev server port (3000)."""

    def test_cors_default_matches_vite_port(self):
        """CORS default must contain port 3000, not 5173."""
        import sys

        # Reload to avoid cached module with old default
        for mod in list(sys.modules.keys()):
            if "runsight_api.core.config" in mod:
                del sys.modules[mod]

        from runsight_api.core.config import Settings

        s = Settings()
        origins = s.cors_origins
        assert isinstance(origins, list), f"cors_origins must be a list, got {type(origins)}"
        assert any("3000" in o for o in origins), (
            f"CORS default must include port 3000 (Vite dev server), got {origins}"
        )
        assert not any("5173" in o for o in origins), (
            f"CORS default must not include stale port 5173, got {origins}"
        )
