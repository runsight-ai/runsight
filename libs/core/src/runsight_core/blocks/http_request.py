"""
HttpRequestBlock — stub for HTTP request execution.

Actual HTTP execution will be implemented in RUN-214.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState


class HttpRequestBlock(BaseBlock):
    """
    Make an HTTP request as part of a workflow.

    This is a stub — execute() raises NotImplementedError.
    Full implementation is tracked under RUN-214.
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

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        raise NotImplementedError(
            f"HttpRequestBlock '{self.block_id}': execute() not yet implemented (see RUN-214)"
        )
