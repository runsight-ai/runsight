"""
HttpRequestBlock — HTTP request execution for workflows.

Implements:
1. Template resolution ({{block_id}} -> state.results[block_id].output)
2. SSRF protection (DNS resolve -> IP check with ipaddress.is_private)
3. Auth header building (bearer, api_key, basic)
4. HTTP execution via httpx.AsyncClient with retry
5. Response parsing (JSON auto-detect, raw text fallback)
6. Return WorkflowState with BlockResult in results
"""

from __future__ import annotations

import base64
import ipaddress
import json
import re
import socket
import time
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlparse

from pydantic import Field, field_validator

import httpx

from runsight_core.blocks.base import BaseBlock
from runsight_core.state import BlockResult, WorkflowState

# Regex to match {{variable_name}} templates
_TEMPLATE_RE = re.compile(r"\{\{(\w+)\}\}")


class HttpRequestError(Exception):
    """Domain error for HTTP request failures."""


class SSRFError(HttpRequestError):
    """Raised when a request targets a private/reserved IP address."""


class TemplateResolutionError(HttpRequestError):
    """Raised when a template variable cannot be resolved from state."""


class HttpStatusError(HttpRequestError):
    """Raised when response status code is not acceptable."""


class HttpRequestBlock(BaseBlock):
    """
    Make an HTTP request as part of a workflow.

    Supports template resolution, SSRF protection, auth headers,
    retry logic, and response parsing.
    """

    def __init__(
        self,
        block_id: str,
        *,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[str] = None,
        body_type: str = "json",
        auth_type: Optional[str] = None,
        auth_config: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 30,
        retry_count: int = 0,
        retry_backoff: float = 1.0,
        expected_status_codes: Optional[List[int]] = None,
        allow_private_ips: bool = False,
    ):
        super().__init__(block_id)
        self.url = url
        self.method = method
        self.headers = headers if headers is not None else {}
        self.body = body
        self.body_type = body_type
        self.auth_type = auth_type
        self.auth_config = auth_config if auth_config is not None else {}
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count
        self.retry_backoff = retry_backoff
        self.expected_status_codes = expected_status_codes
        self.allow_private_ips = allow_private_ips

    # ------------------------------------------------------------------
    # Template resolution
    # ------------------------------------------------------------------

    def _resolve_templates(self, url: str, state: WorkflowState) -> str:
        """Replace {{block_id}} placeholders with state.results[block_id].output.

        Raises:
            TemplateResolutionError: If a referenced block_id is not in state.results.
        """

        def _replacer(match: re.Match) -> str:
            var_name = match.group(1)
            if var_name not in state.results:
                raise TemplateResolutionError(
                    f"Template variable '{{{{{{var_name}}}}}}' not found in state results. "
                    f"Available keys: {list(state.results.keys())}"
                )
            return state.results[var_name].output

        return _TEMPLATE_RE.sub(_replacer, url)

    # ------------------------------------------------------------------
    # SSRF protection
    # ------------------------------------------------------------------

    def _validate_ssrf(self, url: str) -> Optional[str]:
        """Check that the resolved URL does not target a private/reserved IP.

        Returns:
            The resolved IP string to pin for the actual request, or None if
            the URL already contains a literal IP or allow_private_ips is set.

        Raises:
            SSRFError: If the target IP is private/reserved and allow_private_ips is False.
        """
        if self.allow_private_ips:
            return None

        parsed = urlparse(url)
        hostname = parsed.hostname
        if hostname is None:
            raise SSRFError(f"Cannot parse hostname from URL: {url}")

        # Try to parse hostname directly as an IP address first
        try:
            addr = ipaddress.ip_address(hostname)
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                raise SSRFError(
                    f"SSRF blocked: {hostname} resolves to private/reserved address {addr}"
                )
            # Already a literal IP — no rewriting needed
            return None
        except ValueError:
            # Not a literal IP address, need to resolve via DNS
            pass

        # Resolve hostname to IP addresses
        try:
            addrinfos = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            # DNS resolution failed — allow the request through.
            # The HTTP client will handle unreachable hosts.
            return None

        resolved_ip: Optional[str] = None
        for addrinfo in addrinfos:
            ip_str = addrinfo[4][0]
            addr = ipaddress.ip_address(ip_str)
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                raise SSRFError(
                    f"SSRF blocked: {hostname} resolves to private/reserved address {addr}"
                )
            if resolved_ip is None:
                resolved_ip = ip_str

        return resolved_ip

    # ------------------------------------------------------------------
    # Auth header building
    # ------------------------------------------------------------------

    def _build_auth_headers(self) -> Dict[str, str]:
        """Build authentication headers based on auth_type and auth_config.

        Returns:
            Dict of headers to merge into the request.
        """
        if self.auth_type is None:
            return {}

        if self.auth_type == "bearer":
            token = self.auth_config.get("token", "")
            return {"Authorization": f"Bearer {token}"}

        if self.auth_type == "api_key":
            # Support "in": "query" — key is appended as URL query param (handled in execute)
            if self.auth_config.get("in") == "query":
                return {}
            header_name = self.auth_config.get("header", "X-API-Key")
            value = self.auth_config.get("value", "")
            return {header_name: value}

        if self.auth_type == "basic":
            username = self.auth_config.get("username", "")
            password = self.auth_config.get("password", "")
            credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            return {"Authorization": f"Basic {credentials}"}

        return {}

    def _apply_auth_query_params(self, url: str) -> str:
        """Append API key as a query parameter if auth_type=api_key and in=query.

        Returns:
            URL with appended query parameter, or original URL if not applicable.
        """
        if self.auth_type == "api_key" and self.auth_config.get("in") == "query":
            key = self.auth_config.get("key", "")
            separator = "&" if "?" in url else "?"
            return f"{url}{separator}api_key={key}"
        return url

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(response: httpx.Response) -> str:
        """Parse response body: JSON auto-detect, raw text fallback.

        Returns:
            String representation of the response body.
        """
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                data = response.json()
                return json.dumps(data)
            except (json.JSONDecodeError, ValueError):
                return response.text
        return response.text

    # ------------------------------------------------------------------
    # Status code validation
    # ------------------------------------------------------------------

    def _validate_status(self, response: httpx.Response) -> None:
        """Validate response status code.

        Raises:
            HttpStatusError: If status code is not 2xx and not in expected_status_codes.
        """
        status = response.status_code

        # If explicit expected codes are set, accept only those
        if self.expected_status_codes is not None:
            if status in self.expected_status_codes:
                return
            # Fall through to default 2xx check if not in expected list

        # Default: 2xx is success
        if 200 <= status < 300:
            return

        # Check expected_status_codes again for non-2xx
        if self.expected_status_codes is not None and status in self.expected_status_codes:
            return

        raise HttpStatusError(f"HTTP {status}: {response.text[:500]}")

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        """Execute the HTTP request block.

        Steps:
        1. Resolve templates in URL
        2. Validate SSRF
        3. Build auth headers
        4. Execute HTTP request with retry
        5. Parse response and build BlockResult

        Returns:
            New WorkflowState with BlockResult in results[self.block_id].
        """
        # 1. Template resolution
        resolved_url = self._resolve_templates(self.url, state)

        # 2. SSRF protection — returns pinned IP for DNS-resolved hostnames
        pinned_ip = self._validate_ssrf(resolved_url)

        # 3. Auth headers + query params
        auth_headers = self._build_auth_headers()
        merged_headers = {**self.headers, **auth_headers}
        resolved_url = self._apply_auth_query_params(resolved_url)

        # 3b. Pin resolved IP to prevent DNS rebinding TOCTOU
        if pinned_ip is not None:
            parsed = urlparse(resolved_url)
            original_hostname = parsed.hostname
            # Replace hostname with pinned IP, preserving port if present
            if parsed.port:
                new_netloc = f"{pinned_ip}:{parsed.port}"
            else:
                new_netloc = pinned_ip
            resolved_url = parsed._replace(netloc=new_netloc).geturl()
            # Set Host header to original hostname for TLS/SNI and virtual hosting
            if "Host" not in merged_headers:
                merged_headers["Host"] = original_hostname

        # 4. Build request kwargs
        request_kwargs: Dict = {
            "method": self.method.upper(),
            "url": resolved_url,
            "headers": merged_headers,
            "timeout": float(self.timeout_seconds),
        }

        # Add body for methods that support it
        if self.body is not None:
            if self.body_type == "json":
                request_kwargs["content"] = self.body
                if "Content-Type" not in merged_headers:
                    request_kwargs["headers"] = {
                        **merged_headers,
                        "Content-Type": "application/json",
                    }
            elif self.body_type == "form":
                request_kwargs["content"] = self.body
                if "Content-Type" not in merged_headers:
                    request_kwargs["headers"] = {
                        **merged_headers,
                        "Content-Type": "application/x-www-form-urlencoded",
                    }
            else:
                request_kwargs["content"] = self.body

        # 5. Execute with retry
        last_exc: Optional[Exception] = None
        max_attempts = 1 + self.retry_count

        for attempt in range(max_attempts):
            start_time = time.monotonic()
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.request(**request_kwargs)

                elapsed_ms = (time.monotonic() - start_time) * 1000.0

                # Check if we should retry (only 5xx)
                try:
                    self._validate_status(response)
                except HttpStatusError as exc:
                    # Only retry on 5xx
                    if 500 <= response.status_code < 600 and attempt < max_attempts - 1:
                        last_exc = exc
                        continue
                    raise

                # Success path
                output = self._parse_response(response)
                metadata = {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "latency_ms": elapsed_ms,
                }

                block_result = BlockResult(
                    output=output,
                    metadata=metadata,
                )

                return state.model_copy(
                    update={
                        "results": {**state.results, self.block_id: block_result},
                    }
                )

            except httpx.TimeoutException as exc:
                raise HttpRequestError(
                    f"Request timed out after {self.timeout_seconds}s: {exc}"
                ) from exc
            except HttpStatusError:
                raise
            except httpx.HTTPError as exc:
                # Retry connection errors if retries remain
                if attempt < max_attempts - 1:
                    last_exc = HttpRequestError(f"HTTP error: {exc}")
                    last_exc.__cause__ = exc
                    continue
                raise HttpRequestError(f"HTTP error: {exc}") from exc

        # All retries exhausted — re-raise last exception
        if last_exc is not None:
            raise last_exc

        # Should not reach here, but just in case
        raise HttpRequestError("Request failed after all retry attempts")


# ── Schema definition (co-located) ─────────────────────────────────────────

from runsight_core.yaml.schema import BaseBlockDef  # noqa: E402


class HttpRequestBlockDef(BaseBlockDef):
    type: Literal["http_request"] = "http_request"
    url: str
    method: str = "GET"
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[str] = None
    body_type: Literal["json", "form", "raw"] = "json"
    auth_type: Optional[Literal["bearer", "api_key", "basic"]] = None
    auth_config: Dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    retry_count: int = 0
    retry_backoff: float = 1.0
    expected_status_codes: Optional[List[int]] = None
    allow_private_ips: bool = False

    @field_validator("method", mode="before")
    @classmethod
    def _uppercase_method(cls, v: str) -> str:
        v = v.upper()
        allowed = {"GET", "POST", "PUT", "DELETE", "PATCH"}
        if v not in allowed:
            raise ValueError(f"method must be one of {sorted(allowed)}, got '{v}'")
        return v


# Explicit registration: __init_subclass__ cannot detect Literal annotations
# when ``from __future__ import annotations`` is active (PEP 563).
from runsight_core.blocks._registry import register_block_def as _register_block_def  # noqa: E402
from runsight_core.blocks._registry import register_block_builder as _register_builder  # noqa: E402

_register_block_def("http_request", HttpRequestBlockDef)


# ── Builder function ────────────────────────────────────────────────────────


def build(
    block_id: str,
    block_def: Any,
    souls_map: Dict[str, Any],
    runner: Any,
    all_blocks: Dict[str, Any],
) -> HttpRequestBlock:
    """Build an HttpRequestBlock from a block definition."""
    return HttpRequestBlock(
        block_id,
        url=block_def.url,
        method=block_def.method,
        headers=block_def.headers,
        body=block_def.body,
        body_type=block_def.body_type,
        auth_type=block_def.auth_type,
        auth_config=block_def.auth_config,
        timeout_seconds=block_def.timeout_seconds,
        retry_count=block_def.retry_count,
        retry_backoff=block_def.retry_backoff,
        expected_status_codes=block_def.expected_status_codes,
        allow_private_ips=block_def.allow_private_ips,
    )


_register_builder("http_request", build)
