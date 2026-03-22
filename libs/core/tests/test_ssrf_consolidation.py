"""
RUN-249 — Red tests: Consolidate SSRF validation and replace blocking DNS with async.

Two problems being fixed:
(a) `http_request.py` duplicates `security.py` SSRF logic with its own SSRFError class.
(b) Both implementations use blocking `socket.getaddrinfo()` in an async context.

These tests verify the acceptance criteria:
1. Single SSRFError class lives in security.py, NOT duplicated in http_request.py
2. SSRFError does NOT inherit from HttpRequestError
3. DNS resolution uses asyncio.getaddrinfo() (non-blocking)
4. http_request.py imports and uses the shared validate_ssrf from security.py
5. validate_ssrf is an async coroutine

All tests MUST fail because consolidation has not been done yet.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Paths to source files under test
# ---------------------------------------------------------------------------

_CORE_SRC = Path(__file__).resolve().parent.parent / "src" / "runsight_core"
_SECURITY_PY = _CORE_SRC / "security.py"
_HTTP_REQUEST_PY = _CORE_SRC / "blocks" / "http_request.py"


# ===========================================================================
# 1. http_request.py must NOT define its own SSRFError class
# ===========================================================================


class TestNoDuplicateSSRFError:
    """After consolidation, SSRFError should only be defined in security.py."""

    def test_http_request_does_not_define_ssrf_error_class(self):
        """http_request.py must NOT contain a class named SSRFError."""
        source = _HTTP_REQUEST_PY.read_text()
        tree = ast.parse(source)

        class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

        assert "SSRFError" not in class_names, (
            "http_request.py still defines its own SSRFError class; "
            "it should be removed after consolidation"
        )


# ===========================================================================
# 2. http_request.py must NOT define its own _validate_ssrf function
# ===========================================================================


class TestNoDuplicateValidateSSRF:
    """After consolidation, _validate_ssrf should not exist as a method in http_request.py."""

    def test_http_request_does_not_define_validate_ssrf(self):
        """http_request.py must NOT contain a method named _validate_ssrf."""
        source = _HTTP_REQUEST_PY.read_text()
        tree = ast.parse(source)

        function_names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function_names.append(node.name)

        assert "_validate_ssrf" not in function_names, (
            "http_request.py still defines _validate_ssrf; "
            "it should import validate_ssrf from runsight_core.security instead"
        )


# ===========================================================================
# 3. http_request.py imports SSRFError from runsight_core.security
# ===========================================================================


class TestHTTPRequestImportsSharedSSRFError:
    """http_request.py should import SSRFError from the shared security module."""

    def test_http_request_imports_ssrf_error_from_security(self):
        """http_request.py must import SSRFError from runsight_core.security."""
        source = _HTTP_REQUEST_PY.read_text()
        tree = ast.parse(source)

        found_import = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "runsight_core.security" in node.module:
                    imported_names = [alias.name for alias in node.names]
                    if "SSRFError" in imported_names:
                        found_import = True
                        break

        assert found_import, (
            "http_request.py does not import SSRFError from runsight_core.security; "
            "expected 'from runsight_core.security import SSRFError'"
        )

    def test_http_request_imports_validate_ssrf_from_security(self):
        """http_request.py must import validate_ssrf from runsight_core.security."""
        source = _HTTP_REQUEST_PY.read_text()
        tree = ast.parse(source)

        found_import = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "runsight_core.security" in node.module:
                    imported_names = [alias.name for alias in node.names]
                    if "validate_ssrf" in imported_names:
                        found_import = True
                        break

        assert found_import, (
            "http_request.py does not import validate_ssrf from runsight_core.security; "
            "expected 'from runsight_core.security import validate_ssrf'"
        )


# ===========================================================================
# 4. security.py validate_ssrf is an async coroutine
# ===========================================================================


class TestValidateSSRFIsAsync:
    """After consolidation, validate_ssrf must be an async function."""

    def test_validate_ssrf_is_coroutine_function(self):
        """security.py's validate_ssrf must be a coroutine (async def)."""
        from runsight_core.security import validate_ssrf

        assert inspect.iscoroutinefunction(validate_ssrf), (
            "validate_ssrf is not an async function; "
            "it must use 'async def' to support asyncio.getaddrinfo()"
        )

    async def test_validate_ssrf_can_be_awaited(self):
        """validate_ssrf should be awaitable and complete without error for a public IP."""
        from runsight_core.security import validate_ssrf

        # A literal public IP should not raise
        await validate_ssrf("https://8.8.8.8/path")

    async def test_validate_ssrf_raises_ssrf_error_when_awaited(self):
        """validate_ssrf should raise SSRFError for private IPs when awaited."""
        from runsight_core.security import SSRFError, validate_ssrf

        # First verify it is actually a coroutine (not a sync function that
        # happens to raise before we'd notice the missing await).
        assert inspect.iscoroutinefunction(validate_ssrf), (
            "validate_ssrf must be async to be properly awaitable"
        )

        with pytest.raises(SSRFError):
            await validate_ssrf("http://192.168.1.1/evil")


# ===========================================================================
# 5. security.py does NOT use blocking socket.getaddrinfo
# ===========================================================================


class TestNoBlockingDNS:
    """After consolidation, security.py must not call socket.getaddrinfo."""

    def test_security_does_not_use_socket_getaddrinfo(self):
        """security.py must NOT call socket.getaddrinfo (blocking DNS)."""
        source = _SECURITY_PY.read_text()
        tree = ast.parse(source)

        blocking_calls: list[str] = []
        for node in ast.walk(tree):
            # Detect socket.getaddrinfo(...)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if (
                    node.func.attr == "getaddrinfo"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "socket"
                ):
                    blocking_calls.append(f"line {node.lineno}")

        assert not blocking_calls, (
            f"security.py still uses blocking socket.getaddrinfo at {blocking_calls}; "
            "replace with asyncio.getaddrinfo() or loop.getaddrinfo()"
        )

    def test_security_does_not_import_socket(self):
        """security.py should not import socket at all after switching to asyncio DNS."""
        source = _SECURITY_PY.read_text()
        tree = ast.parse(source)

        imports_socket = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "socket":
                        imports_socket = True
            elif isinstance(node, ast.ImportFrom):
                if node.module == "socket":
                    imports_socket = True

        assert not imports_socket, (
            "security.py still imports 'socket'; "
            "after switching to asyncio.getaddrinfo(), the socket import should be removed"
        )


# ===========================================================================
# 6. SSRFError does NOT inherit from HttpRequestError
# ===========================================================================


class TestSSRFErrorInheritance:
    """SSRFError must be independent of the HttpRequestError hierarchy."""

    def test_ssrf_error_does_not_inherit_from_http_request_error(self):
        """SSRFError in security.py must NOT be a subclass of HttpRequestError."""
        from runsight_core.blocks.http_request import HttpRequestError
        from runsight_core.security import SSRFError

        assert not issubclass(SSRFError, HttpRequestError), (
            "SSRFError inherits from HttpRequestError; "
            "it should inherit from Exception directly to stay outside the HTTP error hierarchy"
        )

    def test_ssrf_error_is_exception_subclass(self):
        """SSRFError must still be a subclass of Exception."""
        from runsight_core.security import SSRFError

        assert issubclass(SSRFError, Exception)

    def test_ssrf_error_identity_is_shared(self):
        """The SSRFError used in http_request.py must be the same class as in security.py."""
        from runsight_core.blocks.http_request import SSRFError as HttpSSRFError
        from runsight_core.security import SSRFError as SecuritySSRFError

        assert HttpSSRFError is SecuritySSRFError, (
            "http_request.py's SSRFError is a different class than security.py's SSRFError; "
            "http_request.py should import SSRFError from runsight_core.security"
        )
