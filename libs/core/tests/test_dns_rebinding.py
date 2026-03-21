"""
RUN-226 — Red tests: DNS rebinding TOCTOU attack prevention in HttpRequestBlock.

These tests verify that HttpRequestBlock pins the resolved IP from
_validate_ssrf() and uses it for the actual HTTP request, preventing
a DNS rebinding attack where the hostname resolves to a different
(private) IP between validation and request execution.

Race condition being tested:
  Time 0: _validate_ssrf() -> DNS resolves evil.com -> 1.2.3.4 (public) -> PASS
  Time 1: DNS TTL expires, attacker changes evil.com -> 169.254.169.254
  Time 2: httpx.request() -> DNS resolves evil.com -> 169.254.169.254 -> SSRF!

All tests MUST fail because IP pinning does not exist yet.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from runsight_core.blocks.http_request import (
    HttpRequestBlock,
    SSRFError,
)
from runsight_core.state import BlockResult, WorkflowState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**results: str) -> WorkflowState:
    """Build a WorkflowState with string results keyed by block_id."""
    return WorkflowState(results={k: BlockResult(output=v) for k, v in results.items()})


def _make_block(
    block_id: str = "http1",
    url: str = "https://api.example.com/data",
    method: str = "GET",
    **kwargs,
) -> HttpRequestBlock:
    """Create an HttpRequestBlock with sensible defaults."""
    return HttpRequestBlock(block_id=block_id, url=url, method=method, **kwargs)


def _fake_getaddrinfo_factory(ip_sequence: list[str]):
    """Return a side_effect callable that yields different IPs on successive calls.

    Each call to the returned function pops the next IP from *ip_sequence*.
    The format matches ``socket.getaddrinfo`` return value (list of 5-tuples).
    """
    call_idx = {"n": 0}

    def _fake_getaddrinfo(host, port, *args, **kwargs):
        idx = min(call_idx["n"], len(ip_sequence) - 1)
        ip = ip_sequence[idx]
        call_idx["n"] += 1
        # socket.getaddrinfo returns list of (family, type, proto, canonname, sockaddr)
        # sockaddr for AF_INET is (ip, port)
        return [(2, 1, 6, "", (ip, 0))]

    return _fake_getaddrinfo


def _build_success_response() -> httpx.Response:
    """Build a minimal 200 OK httpx.Response."""
    return httpx.Response(
        200,
        json={"ok": True},
        headers={"Content-Type": "application/json"},
    )


# ===========================================================================
# Test 1: Normal flow works after fix — pinned IP is used for request
# ===========================================================================


class TestNormalFlowWithPinnedIP:
    """After the fix, requests to hostnames should connect to the validated IP."""

    @pytest.mark.asyncio
    async def test_request_uses_pinned_ip_not_hostname(self):
        """When DNS resolves to a public IP, the actual HTTP request must use
        that resolved IP (not the original hostname) so that no second DNS
        lookup can occur.

        This test:
        1. Mocks socket.getaddrinfo to resolve "api.example.com" -> "93.184.216.34"
        2. Intercepts the httpx request to see which URL was actually called
        3. Asserts the request went to the IP, NOT the hostname

        EXPECTED TO FAIL: current code passes the hostname URL to httpx,
        which triggers its own DNS resolution.
        """
        public_ip = "93.184.216.34"
        block = _make_block(url="https://api.example.com/data")
        state = _make_state()

        with patch(
            "socket.getaddrinfo",
            side_effect=_fake_getaddrinfo_factory([public_ip]),
        ):
            # Patch httpx.AsyncClient.request to capture what URL is actually used
            with patch(
                "httpx.AsyncClient.request",
                new_callable=AsyncMock,
            ) as mock_request:
                mock_request.return_value = _build_success_response()

                await block.execute(state)

                # The request should have been made to the resolved IP,
                # not the original hostname
                call_kwargs = mock_request.call_args
                actual_url = str(
                    call_kwargs.kwargs.get(
                        "url", call_kwargs.args[1] if len(call_kwargs.args) > 1 else ""
                    )
                )

                assert public_ip in actual_url, (
                    f"Expected request URL to contain pinned IP {public_ip}, "
                    f"but got: {actual_url}. "
                    "The code is still using the hostname, allowing DNS rebinding."
                )

    @pytest.mark.asyncio
    async def test_successful_execution_returns_block_result(self):
        """After IP pinning, execute() should still return a valid
        WorkflowState with BlockResult containing parsed output.

        This verifies the basic happy path works end-to-end with the fix.
        """
        public_ip = "93.184.216.34"
        block = _make_block(url="https://api.example.com/data")
        state = _make_state()

        with patch(
            "socket.getaddrinfo",
            side_effect=_fake_getaddrinfo_factory([public_ip]),
        ):
            with patch(
                "httpx.AsyncClient.request",
                new_callable=AsyncMock,
            ) as mock_request:
                mock_request.return_value = _build_success_response()

                result = await block.execute(state)

                # Should still produce a valid result
                assert block.block_id in result.results
                block_result = result.results[block.block_id]
                assert block_result.output is not None

                # The pinned IP must appear in the request URL
                call_kwargs = mock_request.call_args
                actual_url = str(
                    call_kwargs.kwargs.get(
                        "url", call_kwargs.args[1] if len(call_kwargs.args) > 1 else ""
                    )
                )
                assert public_ip in actual_url, (
                    f"Request URL should contain pinned IP {public_ip}, but got: {actual_url}"
                )


# ===========================================================================
# Test 2: DNS rebinding attack is prevented
# ===========================================================================


class TestDNSRebindingPrevention:
    """The core TOCTOU test: DNS changes between validate and request."""

    @pytest.mark.asyncio
    async def test_dns_rebinding_uses_first_resolved_ip(self):
        """Simulate DNS rebinding: first resolution returns public IP,
        second returns private IP (AWS metadata endpoint).

        The fix should ensure the HTTP request goes to the FIRST resolved
        IP (public), not the second (private).

        EXPECTED TO FAIL: current code does two independent DNS lookups —
        _validate_ssrf() checks the first, but httpx uses whatever DNS
        returns at request time (the second, attacker-controlled IP).
        """
        public_ip = "93.184.216.34"
        private_ip = "169.254.169.254"  # AWS metadata — link-local

        block = _make_block(url="https://evil.com/latest/meta-data")
        state = _make_state()

        # getaddrinfo returns public IP first (passes validation),
        # then private IP (attacker rebinds DNS)
        with patch(
            "socket.getaddrinfo",
            side_effect=_fake_getaddrinfo_factory([public_ip, private_ip]),
        ):
            with patch(
                "httpx.AsyncClient.request",
                new_callable=AsyncMock,
            ) as mock_request:
                mock_request.return_value = _build_success_response()

                await block.execute(state)

                # The request MUST have been made to the first (validated) IP
                call_kwargs = mock_request.call_args
                actual_url = str(
                    call_kwargs.kwargs.get(
                        "url", call_kwargs.args[1] if len(call_kwargs.args) > 1 else ""
                    )
                )

                assert public_ip in actual_url, (
                    f"Expected request URL to contain pinned IP {public_ip}, "
                    f"but got: {actual_url}. "
                    "DNS rebinding attack would succeed with the current code!"
                )
                assert private_ip not in actual_url, (
                    f"Request URL must NOT contain the rebinding IP {private_ip}. "
                    "The attacker's DNS change was used for the actual request!"
                )

    @pytest.mark.asyncio
    async def test_dns_rebinding_to_loopback_prevented(self):
        """Simulate DNS rebinding from public IP to 127.0.0.1 (loopback).

        Even if the second DNS lookup would resolve to loopback, the request
        should use the first (validated) public IP.
        """
        public_ip = "93.184.216.34"
        loopback_ip = "127.0.0.1"

        block = _make_block(url="https://evil.com/internal")
        state = _make_state()

        with patch(
            "socket.getaddrinfo",
            side_effect=_fake_getaddrinfo_factory([public_ip, loopback_ip]),
        ):
            with patch(
                "httpx.AsyncClient.request",
                new_callable=AsyncMock,
            ) as mock_request:
                mock_request.return_value = _build_success_response()

                await block.execute(state)

                call_kwargs = mock_request.call_args
                actual_url = str(
                    call_kwargs.kwargs.get(
                        "url", call_kwargs.args[1] if len(call_kwargs.args) > 1 else ""
                    )
                )

                assert public_ip in actual_url, (
                    f"Expected pinned IP {public_ip} in request URL, but got: {actual_url}"
                )
                assert loopback_ip not in actual_url, (
                    f"Loopback IP {loopback_ip} must not appear in request URL"
                )

    @pytest.mark.asyncio
    async def test_dns_rebinding_to_internal_network_prevented(self):
        """Simulate DNS rebinding from public IP to 10.0.0.1 (internal network).

        The pinned IP from validation must be used, not the internal IP.
        """
        public_ip = "93.184.216.34"
        internal_ip = "10.0.0.1"

        block = _make_block(url="https://evil.com/admin")
        state = _make_state()

        with patch(
            "socket.getaddrinfo",
            side_effect=_fake_getaddrinfo_factory([public_ip, internal_ip]),
        ):
            with patch(
                "httpx.AsyncClient.request",
                new_callable=AsyncMock,
            ) as mock_request:
                mock_request.return_value = _build_success_response()

                await block.execute(state)

                call_kwargs = mock_request.call_args
                actual_url = str(
                    call_kwargs.kwargs.get(
                        "url", call_kwargs.args[1] if len(call_kwargs.args) > 1 else ""
                    )
                )

                assert public_ip in actual_url, (
                    f"Expected pinned IP {public_ip} in request URL, but got: {actual_url}"
                )
                assert internal_ip not in actual_url, (
                    f"Internal IP {internal_ip} must not appear in request URL"
                )


# ===========================================================================
# Test 3: Host header is preserved when using pinned IP
# ===========================================================================


class TestHostHeaderPreservation:
    """When the URL is rewritten to use the pinned IP, the original hostname
    must still be sent as the Host header for correct TLS/SNI and virtual
    host routing."""

    @pytest.mark.asyncio
    async def test_host_header_contains_original_hostname(self):
        """The Host header must contain the original hostname (api.example.com),
        not the pinned IP address, when the URL is rewritten to the IP.

        EXPECTED TO FAIL: current code does not rewrite the URL to the IP,
        so this test verifies a behavior that the fix must introduce.
        """
        public_ip = "93.184.216.34"
        original_hostname = "api.example.com"
        block = _make_block(url=f"https://{original_hostname}/data")
        state = _make_state()

        with patch(
            "socket.getaddrinfo",
            side_effect=_fake_getaddrinfo_factory([public_ip]),
        ):
            with patch(
                "httpx.AsyncClient.request",
                new_callable=AsyncMock,
            ) as mock_request:
                mock_request.return_value = _build_success_response()

                await block.execute(state)

                call_kwargs = mock_request.call_args
                actual_url = str(
                    call_kwargs.kwargs.get(
                        "url", call_kwargs.args[1] if len(call_kwargs.args) > 1 else ""
                    )
                )

                # URL should be rewritten to the IP
                assert public_ip in actual_url, (
                    f"Expected pinned IP {public_ip} in URL, got: {actual_url}"
                )

                # But the Host header must preserve the original hostname
                headers = call_kwargs.kwargs.get("headers", {})
                host_header = headers.get("Host", "")
                assert original_hostname in host_header, (
                    f"Expected Host header to contain '{original_hostname}', "
                    f"but headers were: {headers}. "
                    "When pinning the IP, the Host header must be set to "
                    "the original hostname for TLS/SNI and virtual hosting."
                )

    @pytest.mark.asyncio
    async def test_host_header_not_overridden_if_user_set(self):
        """If the user explicitly sets a Host header, it should NOT be
        overridden by the IP pinning logic."""
        public_ip = "93.184.216.34"
        custom_host = "custom-host.example.com"
        block = _make_block(
            url="https://api.example.com/data",
            headers={"Host": custom_host},
        )
        state = _make_state()

        with patch(
            "socket.getaddrinfo",
            side_effect=_fake_getaddrinfo_factory([public_ip]),
        ):
            with patch(
                "httpx.AsyncClient.request",
                new_callable=AsyncMock,
            ) as mock_request:
                mock_request.return_value = _build_success_response()

                await block.execute(state)

                call_kwargs = mock_request.call_args

                # URL should still use pinned IP
                actual_url = str(
                    call_kwargs.kwargs.get(
                        "url", call_kwargs.args[1] if len(call_kwargs.args) > 1 else ""
                    )
                )
                assert public_ip in actual_url, f"Expected pinned IP in URL, got: {actual_url}"

                # Host header should be the user's custom value, not auto-set
                headers = call_kwargs.kwargs.get("headers", {})
                host_header = headers.get("Host", "")
                assert host_header == custom_host, (
                    f"Expected user-set Host header '{custom_host}', "
                    f"but got '{host_header}'. User-set Host must not be overridden."
                )


# ===========================================================================
# Test 4: SSRF still blocks private IPs on first resolution
# ===========================================================================


class TestSSRFStillBlocksOnFirstResolution:
    """Verify that the existing SSRF protection is not broken by the fix.
    If DNS resolves to a private IP on the FIRST lookup, it must still
    raise SSRFError."""

    @pytest.mark.asyncio
    async def test_first_resolution_to_link_local_raises_ssrf(self):
        """If DNS resolves to 169.254.169.254 on the first (validation) lookup,
        SSRFError must be raised — the fix should not change this behavior."""
        block = _make_block(url="https://evil.com/metadata")
        state = _make_state()

        with patch(
            "socket.getaddrinfo",
            side_effect=_fake_getaddrinfo_factory(["169.254.169.254"]),
        ):
            with pytest.raises(SSRFError, match="private|reserved|SSRF"):
                await block.execute(state)

    @pytest.mark.asyncio
    async def test_first_resolution_to_loopback_raises_ssrf(self):
        """If DNS resolves to 127.0.0.1 on the first lookup, SSRFError
        must be raised."""
        block = _make_block(url="https://evil.com/localhost-trick")
        state = _make_state()

        with patch(
            "socket.getaddrinfo",
            side_effect=_fake_getaddrinfo_factory(["127.0.0.1"]),
        ):
            with pytest.raises(SSRFError, match="private|reserved|SSRF|loopback"):
                await block.execute(state)

    @pytest.mark.asyncio
    async def test_first_resolution_to_private_10_raises_ssrf(self):
        """If DNS resolves to 10.x.x.x on the first lookup, SSRFError
        must be raised."""
        block = _make_block(url="https://evil.com/internal")
        state = _make_state()

        with patch(
            "socket.getaddrinfo",
            side_effect=_fake_getaddrinfo_factory(["10.0.0.1"]),
        ):
            with pytest.raises(SSRFError, match="private|reserved|SSRF"):
                await block.execute(state)

    @pytest.mark.asyncio
    async def test_literal_private_ip_still_blocked(self):
        """Direct IP URL (http://169.254.169.254/...) should still be blocked
        without even doing DNS resolution — existing behavior preserved."""
        block = _make_block(
            url="http://169.254.169.254/latest/meta-data",
            allow_private_ips=False,
        )
        state = _make_state()

        with pytest.raises(SSRFError, match="private|reserved|SSRF"):
            await block.execute(state)

    @pytest.mark.asyncio
    async def test_allow_private_ips_still_bypasses(self):
        """allow_private_ips=True should still bypass all SSRF checks,
        including IP pinning logic."""
        block = _make_block(
            url="http://localhost/internal-api",
            allow_private_ips=True,
        )
        state = _make_state()

        with patch(
            "httpx.AsyncClient.request",
            new_callable=AsyncMock,
        ) as mock_request:
            mock_request.return_value = _build_success_response()

            # Should not raise — allow_private_ips bypasses SSRF
            result = await block.execute(state)
            assert block.block_id in result.results
