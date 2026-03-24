"""Red tests for RUN-288: Structured logging foundation (structlog + contextvars + Settings).

Tests cover:
- core/context.py: 4 ContextVars + bind/clear helpers
- core/logging.py: configure_logging with JSON and text renderers
- Settings: log_level and log_format fields with env var overrides
- main.py: calls configure_logging at startup
- pyproject.toml: structlog dependency

All tests should FAIL until the implementation is written.
"""

import json


# ---------------------------------------------------------------------------
# Tests — context.py: ContextVars exist and are importable
# ---------------------------------------------------------------------------


class TestContextVarsExist:
    """core/context.py must expose 4 ContextVars with empty-string defaults."""

    def test_context_module_importable(self):
        from runsight_api.core.context import (  # noqa: F401
            request_id,
            run_id,
            block_id,
            workflow_name,
        )

    def test_request_id_default_is_empty_string(self):
        from runsight_api.core.context import request_id

        assert request_id.get() == ""

    def test_run_id_default_is_empty_string(self):
        from runsight_api.core.context import run_id

        assert run_id.get() == ""

    def test_block_id_default_is_empty_string(self):
        from runsight_api.core.context import block_id

        assert block_id.get() == ""

    def test_workflow_name_default_is_empty_string(self):
        from runsight_api.core.context import workflow_name

        assert workflow_name.get() == ""


# ---------------------------------------------------------------------------
# Tests — context.py: bind/clear helpers
# ---------------------------------------------------------------------------


class TestBindRequestContext:
    """bind_request_context sets request_id."""

    def test_sets_request_id(self):
        from runsight_api.core.context import bind_request_context, request_id

        bind_request_context("req-abc-123")
        assert request_id.get() == "req-abc-123"


class TestBindExecutionContext:
    """bind_execution_context sets run_id and workflow_name."""

    def test_sets_run_id_and_workflow_name(self):
        from runsight_api.core.context import (
            bind_execution_context,
            run_id,
            workflow_name,
        )

        bind_execution_context(run_id="run-42", workflow_name="my_pipeline")
        assert run_id.get() == "run-42"
        assert workflow_name.get() == "my_pipeline"


class TestBindBlockContext:
    """bind_block_context sets block_id."""

    def test_sets_block_id(self):
        from runsight_api.core.context import bind_block_context, block_id

        bind_block_context("blk-99")
        assert block_id.get() == "blk-99"


class TestClearBlockContext:
    """clear_block_context resets block_id but leaves run_id intact."""

    def test_resets_block_id_to_empty(self):
        from runsight_api.core.context import (
            bind_execution_context,
            bind_block_context,
            clear_block_context,
            block_id,
        )

        bind_execution_context(run_id="run-1", workflow_name="wf")
        bind_block_context("blk-1")
        clear_block_context()
        assert block_id.get() == ""

    def test_preserves_run_id(self):
        from runsight_api.core.context import (
            bind_execution_context,
            bind_block_context,
            clear_block_context,
            run_id,
        )

        bind_execution_context(run_id="run-1", workflow_name="wf")
        bind_block_context("blk-1")
        clear_block_context()
        assert run_id.get() == "run-1"


class TestClearExecutionContext:
    """clear_execution_context resets run_id, workflow_name, and block_id."""

    def test_resets_run_id(self):
        from runsight_api.core.context import (
            bind_execution_context,
            clear_execution_context,
            run_id,
        )

        bind_execution_context(run_id="run-1", workflow_name="wf")
        clear_execution_context()
        assert run_id.get() == ""

    def test_resets_workflow_name(self):
        from runsight_api.core.context import (
            bind_execution_context,
            clear_execution_context,
            workflow_name,
        )

        bind_execution_context(run_id="run-1", workflow_name="wf")
        clear_execution_context()
        assert workflow_name.get() == ""

    def test_resets_block_id(self):
        from runsight_api.core.context import (
            bind_execution_context,
            bind_block_context,
            clear_execution_context,
            block_id,
        )

        bind_execution_context(run_id="run-1", workflow_name="wf")
        bind_block_context("blk-1")
        clear_execution_context()
        assert block_id.get() == ""


# ---------------------------------------------------------------------------
# Tests — logging.py: importable and configure_logging function
# ---------------------------------------------------------------------------


class TestLoggingModuleImportable:
    """core/logging.py must expose configure_logging."""

    def test_configure_logging_importable(self):
        from runsight_api.core.logging import configure_logging

        assert callable(configure_logging)


class TestConfigureLoggingJson:
    """configure_logging with JSON format produces JSON log output."""

    def test_json_output_has_required_keys(self, capsys):
        import structlog
        from runsight_api.core.logging import configure_logging

        configure_logging("INFO", "json")
        logger = structlog.get_logger("test.json")
        logger.info("hello_json")

        captured = capsys.readouterr()
        line = captured.err.strip().split("\n")[-1] if captured.err.strip() else ""
        if not line:
            line = captured.out.strip().split("\n")[-1] if captured.out.strip() else ""

        assert line, "Expected log output but got nothing"
        record = json.loads(line)
        assert "timestamp" in record, "JSON log must contain 'timestamp'"
        assert "level" in record, "JSON log must contain 'level'"
        assert "logger" in record, "JSON log must contain 'logger'"
        assert "event" in record, "JSON log must contain 'event'"
        assert record["event"] == "hello_json"


class TestConfigureLoggingText:
    """configure_logging with text format produces human-readable output."""

    def test_text_output_is_not_json(self, capsys):
        import structlog
        from runsight_api.core.logging import configure_logging

        configure_logging("DEBUG", "text")
        logger = structlog.get_logger("test.text")
        logger.debug("hello_text")

        captured = capsys.readouterr()
        output = captured.err + captured.out
        assert "hello_text" in output, "Text log must contain the event message"

        # Text output should NOT be valid JSON
        for line in output.strip().split("\n"):
            if "hello_text" in line:
                try:
                    json.loads(line)
                    raise AssertionError("Text format log line should not be valid JSON")
                except json.JSONDecodeError:
                    pass  # Expected — not JSON


# ---------------------------------------------------------------------------
# Tests — ContextVars injected into log entries
# ---------------------------------------------------------------------------


class TestContextVarsInjectedIntoLogs:
    """When ContextVars are set, they appear in structured log entries."""

    def test_request_id_appears_in_json_log(self, capsys):
        import structlog
        from runsight_api.core.logging import configure_logging
        from runsight_api.core.context import bind_request_context

        configure_logging("INFO", "json")
        bind_request_context("req-in-log")
        logger = structlog.get_logger("test.ctx")
        logger.info("with_context")

        captured = capsys.readouterr()
        output = captured.err + captured.out
        last_line = [line for line in output.strip().split("\n") if "with_context" in line][-1]
        record = json.loads(last_line)
        assert record.get("request_id") == "req-in-log"

    def test_execution_context_appears_in_json_log(self, capsys):
        import structlog
        from runsight_api.core.logging import configure_logging
        from runsight_api.core.context import bind_execution_context

        configure_logging("INFO", "json")
        bind_execution_context(run_id="run-log", workflow_name="wf-log")
        logger = structlog.get_logger("test.exec_ctx")
        logger.info("exec_context_test")

        captured = capsys.readouterr()
        output = captured.err + captured.out
        last_line = [line for line in output.strip().split("\n") if "exec_context_test" in line][-1]
        record = json.loads(last_line)
        assert record.get("run_id") == "run-log"
        assert record.get("workflow_name") == "wf-log"


# ---------------------------------------------------------------------------
# Tests — Settings: log_level and log_format fields
# ---------------------------------------------------------------------------


class TestSettingsLogFields:
    """Settings must have log_level and log_format with correct defaults."""

    def test_settings_has_log_level(self):
        from runsight_api.core.config import Settings

        s = Settings()
        assert hasattr(s, "log_level")

    def test_log_level_default_is_info(self):
        from runsight_api.core.config import Settings

        s = Settings()
        assert s.log_level == "INFO"

    def test_settings_has_log_format(self):
        from runsight_api.core.config import Settings

        s = Settings()
        assert hasattr(s, "log_format")

    def test_log_format_default_is_json(self):
        from runsight_api.core.config import Settings

        s = Settings()
        assert s.log_format == "json"


class TestSettingsLogEnvOverrides:
    """RUNSIGHT_LOG_LEVEL and RUNSIGHT_LOG_FORMAT env vars override defaults."""

    def test_log_level_env_override(self, monkeypatch):
        monkeypatch.setenv("RUNSIGHT_LOG_LEVEL", "DEBUG")
        from runsight_api.core.config import Settings

        s = Settings()
        assert s.log_level == "DEBUG"

    def test_log_format_env_override(self, monkeypatch):
        monkeypatch.setenv("RUNSIGHT_LOG_FORMAT", "text")
        from runsight_api.core.config import Settings

        s = Settings()
        assert s.log_format == "text"


# ---------------------------------------------------------------------------
# Tests — structlog in pyproject.toml
# ---------------------------------------------------------------------------


class TestStructlogDependency:
    """structlog must be listed in pyproject.toml dependencies."""

    def test_structlog_in_dependencies(self):
        from pathlib import Path

        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        content = pyproject.read_text()
        assert "structlog" in content, "structlog must be listed as a dependency in pyproject.toml"


# ---------------------------------------------------------------------------
# Tests — main.py calls configure_logging at startup
# ---------------------------------------------------------------------------


class TestMainCallsConfigureLogging:
    """main.py must call configure_logging during app creation."""

    def test_main_imports_configure_logging(self):
        """main.py source must import configure_logging."""
        import inspect
        from runsight_api import main

        source = inspect.getsource(main)
        assert "configure_logging" in source, "main.py must import or call configure_logging"

    def test_main_invokes_configure_logging(self):
        """main.py must actually call configure_logging (not just import it)."""
        import inspect
        from runsight_api import main

        source = inspect.getsource(main)
        # Look for a call pattern: configure_logging(
        assert "configure_logging(" in source, "main.py must call configure_logging() at startup"
