"""ToolScanner surfaces Pydantic validation errors from isolated custom tool fixtures."""

from __future__ import annotations

import pydantic
import pytest
from tool_validation_helpers import write_tool_yaml


def _exception_chain(exc: BaseException) -> list[BaseException]:
    chain = []
    while exc is not None:
        chain.append(exc)
        exc = exc.__cause__ or exc.__context__  # type: ignore[assignment]
    return chain


@pytest.mark.parametrize(
    ("filename", "yaml_content"),
    [
        (
            "profile_lookup_tool.yaml",
            """
            version: "1.0"
            id: profile_lookup_tool
            kind: tool
            type: custom
            executor: python
            name: Profile Lookup
            description: Returns profile data.
            parameters:
              type: object
            code: |
              def main(args):
                  return args
            bogus_extra_field: should_fail
            """,
        ),
        (
            "profile_missing_name_tool.yaml",
            """
            version: "1.0"
            id: profile_missing_name_tool
            kind: tool
            type: custom
            executor: python
            description: Returns profile data without a name field.
            parameters:
              type: object
            code: |
              def main(args):
                  return args
            """,
        ),
        (
            "profile_request_tool.yaml",
            """
            version: "1.0"
            id: profile_request_tool
            kind: tool
            type: custom
            executor: request
            name: Profile Request
            description: Fetches profile data from a local harness.
            parameters:
              type: object
            request:
              method: GET
              url: http://127.0.0.1:18080/api
              unsupported_extra: oops
            """,
        ),
    ],
)
def test_tool_scanner_validation_errors_include_pydantic_validation_error(
    tmp_path,
    filename: str,
    yaml_content: str,
) -> None:
    from runsight_core.yaml.discovery import ToolScanner

    write_tool_yaml(tmp_path, filename, yaml_content)

    with pytest.raises(Exception) as exc_info:
        ToolScanner(tmp_path).scan()

    assert any(
        isinstance(exc, pydantic.ValidationError) for exc in _exception_chain(exc_info.value)
    )
