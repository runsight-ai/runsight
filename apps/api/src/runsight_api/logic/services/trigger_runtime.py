from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any, Mapping


SENSITIVE_INPUT_KEY_PARTS = (
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "bearer",
    "client_secret",
    "credential",
    "key",
    "password",
    "secret",
    "token",
)
SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "proxy-authorization",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
}
REDACTED = "[redacted]"


@dataclass(frozen=True, slots=True)
class TriggerRuntimeConfig:
    external_invocation_enabled: bool
    max_concurrent_runs: int
    max_pending_external_invocations: int
    body_limit_bytes: int
    public_base_url: str | None = None
    tunnel_base_url: str | None = None
    proxy_base_url: str | None = None

    @classmethod
    def from_settings(cls, settings: Any) -> TriggerRuntimeConfig:
        return cls(
            external_invocation_enabled=bool(settings.external_invocation_enabled),
            max_concurrent_runs=int(settings.max_concurrent_runs),
            max_pending_external_invocations=int(settings.max_pending_external_invocations),
            body_limit_bytes=int(settings.external_invocation_body_limit_bytes),
            public_base_url=settings.public_base_url,
        )

    @property
    def external_invocation_available(self) -> bool:
        return self.external_invocation_enabled

    @property
    def public_base_url_explicit(self) -> bool:
        return self.public_base_url is not None

    @property
    def tunnel_explicit(self) -> bool:
        return self.tunnel_base_url is not None

    @property
    def proxy_explicit(self) -> bool:
        return self.proxy_base_url is not None

    @property
    def public_exposure_explicit(self) -> bool:
        return self.public_base_url_explicit or self.tunnel_explicit or self.proxy_explicit


@dataclass(frozen=True, slots=True)
class ExternalInvocationAdmissionDecision:
    allowed: bool
    failure_code: str | None = None
    status_code: int | None = None
    reason: str | None = None


class ExternalInvocationAdmission:
    def __init__(
        self,
        config: TriggerRuntimeConfig,
        *,
        pending_external_invocations: int = 0,
    ) -> None:
        self.config = config
        self._pending_external_invocations = pending_external_invocations
        self._lock = Lock()

    def check_external_invocation(self, invocation: Any) -> ExternalInvocationAdmissionDecision:
        del invocation
        if not self.config.external_invocation_available:
            return ExternalInvocationAdmissionDecision(
                allowed=False,
                failure_code="runtime_unavailable",
                status_code=503,
                reason="external invocation disabled by runtime config",
            )

        with self._lock:
            pending = self._pending_external_invocations
        if pending >= self.config.max_pending_external_invocations:
            return ExternalInvocationAdmissionDecision(
                allowed=False,
                failure_code="admission_saturated",
                status_code=429,
                reason="external invocation admission is saturated",
            )

        return ExternalInvocationAdmissionDecision(allowed=True)


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).lower().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_INPUT_KEY_PARTS)


def _redact_mapping_values(values: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in values.items():
        if _is_sensitive_key(key):
            redacted[str(key)] = REDACTED
        elif isinstance(value, Mapping):
            redacted[str(key)] = _redact_mapping_values(value)
        else:
            redacted[str(key)] = value
    return redacted


def _redact_headers(headers: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in headers.items():
        header_name = str(key).lower()
        redacted[str(key)] = (
            REDACTED
            if header_name in SENSITIVE_HEADER_NAMES or _is_sensitive_key(header_name)
            else value
        )
    return redacted


def redact_external_invocation_log_context(
    *,
    method: str,
    path: str,
    headers: Mapping[str, Any],
    body: bytes | None,
    inputs: Mapping[str, Any] | None,
) -> dict[str, Any]:
    del body
    return {
        "method": method,
        "path": path,
        "headers": _redact_headers(headers),
        "raw_body": REDACTED,
        "inputs": _redact_mapping_values(inputs or {}),
    }
