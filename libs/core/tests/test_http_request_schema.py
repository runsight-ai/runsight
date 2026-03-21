"""
RUN-215 — Red tests: HTTP block schema + parser registration.

These tests cover:
1. Schema: HttpRequestBlockDef with minimal valid data (type + url, all defaults)
2. Schema: HttpRequestBlockDef with all fields populated
3. Schema: method validation — valid methods pass, invalid (TRACE) rejects, lowercase uppercased
4. Schema: body_type validation — valid types pass, invalid rejects
5. Schema: auth_type validation — valid types pass, None passes, invalid (oauth) rejects
6. Schema: timeout_seconds validation — valid range (1-300), 0 rejects, 301 rejects
7. Schema: default values correct (method=GET, timeout=30, retry_count=0, etc.)
8. Discriminated union: type "http_request" routes to HttpRequestBlockDef
9. Discriminated union: full YAML with http_request block parses via RunsightWorkflowFile
10. Parser: "http_request" exists in BLOCK_TYPE_REGISTRY
11. Parser: _build_http_request creates an HttpRequestBlock instance
12. Parser: built block has correct block_id and config values
13. JSON schema: HttpRequestBlockDef appears in generated JSON schema
14. Extra fields: extra="forbid" rejects unknown fields (inherited pattern)

Imports are deferred to test bodies so each test fails individually with a clear
error rather than blocking the entire module at collection time.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from pydantic import TypeAdapter, ValidationError

from runsight_core.yaml.schema import BlockDef, RunsightWorkflowFile
from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY as BLOCK_TYPE_REGISTRY
from runsight_core.yaml.parser import parse_workflow_yaml

# Shared TypeAdapter for the discriminated union
block_adapter = TypeAdapter(BlockDef)


def _validate_block(data: dict):
    """Validate a dict as a BlockDef via the discriminated union."""
    return block_adapter.validate_python(data)


def _import_http_request_block_def():
    """Import HttpRequestBlockDef from schema; raises ImportError if not yet implemented."""
    from runsight_core.blocks.http_request import HttpRequestBlockDef

    return HttpRequestBlockDef


def _import_http_request_block():
    """Import HttpRequestBlock from blocks; raises ImportError if not yet implemented."""
    from runsight_core.blocks.http_request import HttpRequestBlock

    return HttpRequestBlock


# ===========================================================================
# YAML fixture used by parser tests
# ===========================================================================

VALID_HTTP_REQUEST_YAML = """\
version: "1.0"
config:
  model_name: gpt-4o
blocks:
  fetch_data:
    type: http_request
    url: https://api.example.com/v1/data
    method: POST
    headers:
      Content-Type: application/json
      Authorization: Bearer sk-test
    body: '{"query": "test"}'
    body_type: json
    timeout_seconds: 60
    retry_count: 2
    retry_backoff: 1.5
workflow:
  name: test_http
  entry: fetch_data
  transitions:
    - from: fetch_data
      to: null
"""


# ===========================================================================
# 1. Minimal valid — just type + url, all defaults applied
# ===========================================================================


class TestHttpRequestMinimalValid:
    def test_minimal_valid_instance(self):
        """HttpRequestBlockDef(type='http_request', url='...') must validate."""
        HttpRequestBlockDef = _import_http_request_block_def()
        block = HttpRequestBlockDef(type="http_request", url="https://api.example.com")
        assert block.type == "http_request"
        assert block.url == "https://api.example.com"

    def test_minimal_defaults(self):
        """All optional fields must have correct defaults."""
        HttpRequestBlockDef = _import_http_request_block_def()
        block = HttpRequestBlockDef(type="http_request", url="https://api.example.com")
        assert block.method == "GET"
        assert block.headers == {}
        assert block.body is None
        assert block.body_type == "json"
        assert block.auth_type is None
        assert block.auth_config == {}
        assert block.timeout_seconds == 30
        assert block.retry_count == 0
        assert block.retry_backoff == 1.0
        assert block.expected_status_codes is None
        assert block.allow_private_ips is False

    def test_url_is_required(self):
        """HttpRequestBlockDef without url must raise ValidationError."""
        HttpRequestBlockDef = _import_http_request_block_def()
        with pytest.raises(ValidationError, match="url"):
            HttpRequestBlockDef(type="http_request")


# ===========================================================================
# 2. Full valid — all fields populated
# ===========================================================================


class TestHttpRequestFullValid:
    def test_all_fields_populated(self):
        """HttpRequestBlockDef with all fields explicitly set must validate."""
        HttpRequestBlockDef = _import_http_request_block_def()
        block = HttpRequestBlockDef(
            type="http_request",
            url="https://api.example.com/v1/resource",
            method="POST",
            headers={"Content-Type": "application/json", "X-Custom": "value"},
            body='{"key": "value"}',
            body_type="json",
            auth_type="bearer",
            auth_config={"token": "sk-abc123"},
            timeout_seconds=60,
            retry_count=3,
            retry_backoff=2.0,
            expected_status_codes=[200, 201],
            allow_private_ips=True,
        )
        assert block.url == "https://api.example.com/v1/resource"
        assert block.method == "POST"
        assert block.headers == {"Content-Type": "application/json", "X-Custom": "value"}
        assert block.body == '{"key": "value"}'
        assert block.body_type == "json"
        assert block.auth_type == "bearer"
        assert block.auth_config == {"token": "sk-abc123"}
        assert block.timeout_seconds == 60
        assert block.retry_count == 3
        assert block.retry_backoff == 2.0
        assert block.expected_status_codes == [200, 201]
        assert block.allow_private_ips is True


# ===========================================================================
# 3. Method validation
# ===========================================================================


class TestHttpRequestMethodValidation:
    @pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE", "PATCH"])
    def test_valid_methods_accepted(self, method: str):
        """All five standard HTTP methods must be accepted."""
        HttpRequestBlockDef = _import_http_request_block_def()
        block = HttpRequestBlockDef(type="http_request", url="https://x.com", method=method)
        assert block.method == method

    def test_invalid_method_trace_rejected(self):
        """TRACE is not an allowed method and must raise ValidationError."""
        HttpRequestBlockDef = _import_http_request_block_def()
        with pytest.raises(ValidationError):
            HttpRequestBlockDef(type="http_request", url="https://x.com", method="TRACE")

    def test_invalid_method_options_rejected(self):
        """OPTIONS is not an allowed method and must raise ValidationError."""
        HttpRequestBlockDef = _import_http_request_block_def()
        with pytest.raises(ValidationError):
            HttpRequestBlockDef(type="http_request", url="https://x.com", method="OPTIONS")

    def test_invalid_method_head_rejected(self):
        """HEAD is not an allowed method and must raise ValidationError."""
        HttpRequestBlockDef = _import_http_request_block_def()
        with pytest.raises(ValidationError):
            HttpRequestBlockDef(type="http_request", url="https://x.com", method="HEAD")

    def test_lowercase_method_uppercased(self):
        """method='get' (lowercase) must be uppercased to 'GET'."""
        HttpRequestBlockDef = _import_http_request_block_def()
        block = HttpRequestBlockDef(type="http_request", url="https://x.com", method="get")
        assert block.method == "GET"

    def test_mixed_case_method_uppercased(self):
        """method='Post' (mixed case) must be uppercased to 'POST'."""
        HttpRequestBlockDef = _import_http_request_block_def()
        block = HttpRequestBlockDef(type="http_request", url="https://x.com", method="Post")
        assert block.method == "POST"

    def test_lowercase_invalid_method_still_rejected(self):
        """method='trace' (lowercase of invalid) must still be rejected."""
        HttpRequestBlockDef = _import_http_request_block_def()
        with pytest.raises(ValidationError):
            HttpRequestBlockDef(type="http_request", url="https://x.com", method="trace")


# ===========================================================================
# 4. body_type validation
# ===========================================================================


class TestHttpRequestBodyTypeValidation:
    @pytest.mark.parametrize("body_type", ["json", "form", "raw"])
    def test_valid_body_types_accepted(self, body_type: str):
        """Valid body_type values must be accepted."""
        HttpRequestBlockDef = _import_http_request_block_def()
        block = HttpRequestBlockDef(type="http_request", url="https://x.com", body_type=body_type)
        assert block.body_type == body_type

    def test_invalid_body_type_rejected(self):
        """An invalid body_type like 'xml' must raise ValidationError."""
        HttpRequestBlockDef = _import_http_request_block_def()
        with pytest.raises(ValidationError):
            HttpRequestBlockDef(type="http_request", url="https://x.com", body_type="xml")

    def test_invalid_body_type_multipart_rejected(self):
        """body_type='multipart' is not allowed."""
        HttpRequestBlockDef = _import_http_request_block_def()
        with pytest.raises(ValidationError):
            HttpRequestBlockDef(type="http_request", url="https://x.com", body_type="multipart")


# ===========================================================================
# 5. auth_type validation
# ===========================================================================


class TestHttpRequestAuthTypeValidation:
    @pytest.mark.parametrize("auth_type", ["bearer", "api_key", "basic"])
    def test_valid_auth_types_accepted(self, auth_type: str):
        """Valid auth_type values must be accepted."""
        HttpRequestBlockDef = _import_http_request_block_def()
        block = HttpRequestBlockDef(type="http_request", url="https://x.com", auth_type=auth_type)
        assert block.auth_type == auth_type

    def test_none_auth_type_accepted(self):
        """auth_type=None must be accepted (default)."""
        HttpRequestBlockDef = _import_http_request_block_def()
        block = HttpRequestBlockDef(type="http_request", url="https://x.com", auth_type=None)
        assert block.auth_type is None

    def test_invalid_auth_type_oauth_rejected(self):
        """auth_type='oauth' is not allowed and must raise ValidationError."""
        HttpRequestBlockDef = _import_http_request_block_def()
        with pytest.raises(ValidationError):
            HttpRequestBlockDef(type="http_request", url="https://x.com", auth_type="oauth")

    def test_invalid_auth_type_custom_rejected(self):
        """auth_type='custom' is not allowed."""
        HttpRequestBlockDef = _import_http_request_block_def()
        with pytest.raises(ValidationError):
            HttpRequestBlockDef(type="http_request", url="https://x.com", auth_type="custom")


# ===========================================================================
# 6. timeout_seconds validation
# ===========================================================================


class TestHttpRequestTimeoutValidation:
    def test_default_timeout_is_30(self):
        """Default timeout_seconds must be 30."""
        HttpRequestBlockDef = _import_http_request_block_def()
        block = HttpRequestBlockDef(type="http_request", url="https://x.com")
        assert block.timeout_seconds == 30

    def test_valid_timeout_1(self):
        """timeout_seconds=1 (minimum) must be accepted."""
        HttpRequestBlockDef = _import_http_request_block_def()
        block = HttpRequestBlockDef(type="http_request", url="https://x.com", timeout_seconds=1)
        assert block.timeout_seconds == 1

    def test_valid_timeout_300(self):
        """timeout_seconds=300 (maximum) must be accepted."""
        HttpRequestBlockDef = _import_http_request_block_def()
        block = HttpRequestBlockDef(type="http_request", url="https://x.com", timeout_seconds=300)
        assert block.timeout_seconds == 300

    def test_valid_timeout_150(self):
        """timeout_seconds=150 (mid-range) must be accepted."""
        HttpRequestBlockDef = _import_http_request_block_def()
        block = HttpRequestBlockDef(type="http_request", url="https://x.com", timeout_seconds=150)
        assert block.timeout_seconds == 150

    def test_timeout_0_rejected(self):
        """timeout_seconds=0 is below minimum (1) and must raise ValidationError."""
        HttpRequestBlockDef = _import_http_request_block_def()
        with pytest.raises(ValidationError):
            HttpRequestBlockDef(type="http_request", url="https://x.com", timeout_seconds=0)

    def test_timeout_negative_rejected(self):
        """timeout_seconds=-5 must raise ValidationError."""
        HttpRequestBlockDef = _import_http_request_block_def()
        with pytest.raises(ValidationError):
            HttpRequestBlockDef(type="http_request", url="https://x.com", timeout_seconds=-5)

    def test_timeout_301_rejected(self):
        """timeout_seconds=301 is above maximum (300) and must raise ValidationError."""
        HttpRequestBlockDef = _import_http_request_block_def()
        with pytest.raises(ValidationError):
            HttpRequestBlockDef(type="http_request", url="https://x.com", timeout_seconds=301)

    def test_timeout_1000_rejected(self):
        """timeout_seconds=1000 must raise ValidationError."""
        HttpRequestBlockDef = _import_http_request_block_def()
        with pytest.raises(ValidationError):
            HttpRequestBlockDef(type="http_request", url="https://x.com", timeout_seconds=1000)


# ===========================================================================
# 7. Edge cases
# ===========================================================================


class TestHttpRequestEdgeCases:
    def test_empty_headers_valid(self):
        """headers={} (empty dict) must be valid."""
        HttpRequestBlockDef = _import_http_request_block_def()
        block = HttpRequestBlockDef(type="http_request", url="https://x.com", headers={})
        assert block.headers == {}

    def test_body_with_get_method_valid(self):
        """body provided for GET method must be valid (no method/body coupling)."""
        HttpRequestBlockDef = _import_http_request_block_def()
        block = HttpRequestBlockDef(
            type="http_request",
            url="https://x.com",
            method="GET",
            body='{"filter": "active"}',
        )
        assert block.body == '{"filter": "active"}'
        assert block.method == "GET"

    def test_extra_fields_rejected(self):
        """Unknown fields must be rejected (extra='forbid' inherited from BaseBlockDef)."""
        HttpRequestBlockDef = _import_http_request_block_def()
        with pytest.raises(ValidationError, match="unknown_field"):
            HttpRequestBlockDef(
                type="http_request",
                url="https://x.com",
                unknown_field="bad",
            )

    def test_empty_auth_config_valid(self):
        """auth_config={} (empty dict) must be valid."""
        HttpRequestBlockDef = _import_http_request_block_def()
        block = HttpRequestBlockDef(type="http_request", url="https://x.com", auth_config={})
        assert block.auth_config == {}

    def test_expected_status_codes_list(self):
        """expected_status_codes with a list of ints must be valid."""
        HttpRequestBlockDef = _import_http_request_block_def()
        block = HttpRequestBlockDef(
            type="http_request",
            url="https://x.com",
            expected_status_codes=[200, 201, 204],
        )
        assert block.expected_status_codes == [200, 201, 204]


# ===========================================================================
# 8. Discriminated union — type: "http_request" routes correctly
# ===========================================================================


class TestHttpRequestDiscriminatedUnion:
    def test_union_routes_to_http_request(self):
        """BlockDef discriminated union must route type='http_request' to HttpRequestBlockDef."""
        HttpRequestBlockDef = _import_http_request_block_def()
        block = _validate_block({"type": "http_request", "url": "https://api.example.com"})
        assert isinstance(block, HttpRequestBlockDef)

    def test_union_preserves_fields(self):
        """Fields must be preserved when parsed via the discriminated union."""
        HttpRequestBlockDef = _import_http_request_block_def()
        block = _validate_block(
            {
                "type": "http_request",
                "url": "https://api.example.com",
                "method": "POST",
                "timeout_seconds": 60,
            }
        )
        assert isinstance(block, HttpRequestBlockDef)
        assert block.url == "https://api.example.com"
        assert block.method == "POST"
        assert block.timeout_seconds == 60

    def test_union_rejects_extra_fields(self):
        """Extra fields must be rejected via the discriminated union path too."""
        _import_http_request_block_def()  # Ensure the type exists
        with pytest.raises(ValidationError, match="bogus_field"):
            _validate_block(
                {
                    "type": "http_request",
                    "url": "https://api.example.com",
                    "bogus_field": "nope",
                }
            )


# ===========================================================================
# 9. Full YAML parsing via RunsightWorkflowFile
# ===========================================================================


class TestHttpRequestWorkflowFileParsing:
    def test_workflow_file_validates_http_request_block(self):
        """RunsightWorkflowFile must accept a blocks dict with type: http_request."""
        HttpRequestBlockDef = _import_http_request_block_def()
        wf = RunsightWorkflowFile.model_validate(
            {
                "workflow": {"name": "test", "entry": "b1"},
                "blocks": {
                    "b1": {"type": "http_request", "url": "https://api.example.com"},
                },
            }
        )
        assert "b1" in wf.blocks
        assert isinstance(wf.blocks["b1"], HttpRequestBlockDef)

    def test_workflow_file_mixed_block_types(self):
        """RunsightWorkflowFile must handle http_request alongside other block types."""
        HttpRequestBlockDef = _import_http_request_block_def()
        wf = RunsightWorkflowFile.model_validate(
            {
                "workflow": {"name": "test", "entry": "b1"},
                "blocks": {
                    "b1": {"type": "http_request", "url": "https://api.example.com"},
                    "b2": {"type": "code", "code": "def main(data): return {}"},
                },
            }
        )
        assert isinstance(wf.blocks["b1"], HttpRequestBlockDef)
        assert not isinstance(wf.blocks["b2"], HttpRequestBlockDef)

    def test_parse_workflow_yaml_with_http_request(self):
        """parse_workflow_yaml must successfully parse YAML containing an http_request block."""
        from runsight_core.workflow import Workflow

        wf = parse_workflow_yaml(VALID_HTTP_REQUEST_YAML)
        assert isinstance(wf, Workflow)
        assert wf.name == "test_http"


# ===========================================================================
# 10. Parser registration — BLOCK_TYPE_REGISTRY
# ===========================================================================


class TestHttpRequestParserRegistration:
    def test_http_request_in_block_registry(self):
        """BLOCK_TYPE_REGISTRY must contain an 'http_request' builder."""
        assert "http_request" in BLOCK_TYPE_REGISTRY

    def test_http_request_builder_is_callable(self):
        """The 'http_request' builder must be callable."""
        assert callable(BLOCK_TYPE_REGISTRY["http_request"])


# ===========================================================================
# 11. Parser builder — _build_http_request creates HttpRequestBlock
# ===========================================================================


class TestHttpRequestBuilder:
    def test_builder_returns_http_request_block_instance(self):
        """Calling BLOCK_TYPE_REGISTRY['http_request'] must return an HttpRequestBlock."""
        HttpRequestBlock = _import_http_request_block()
        block_def = MagicMock()
        block_def.type = "http_request"
        block_def.url = "https://api.example.com"
        block_def.method = "GET"
        block_def.headers = {}
        block_def.body = None
        block_def.body_type = "json"
        block_def.auth_type = None
        block_def.auth_config = {}
        block_def.timeout_seconds = 30
        block_def.retry_count = 0
        block_def.retry_backoff = 1.0
        block_def.expected_status_codes = None
        block_def.allow_private_ips = False

        builder = BLOCK_TYPE_REGISTRY["http_request"]
        result = builder("fetch_block", block_def, {}, MagicMock(), {})

        assert isinstance(result, HttpRequestBlock)

    def test_builder_sets_correct_block_id(self):
        """The built HttpRequestBlock must have the correct block_id."""
        HttpRequestBlock = _import_http_request_block()
        block_def = MagicMock()
        block_def.type = "http_request"
        block_def.url = "https://api.example.com/data"
        block_def.method = "POST"
        block_def.headers = {"X-Key": "val"}
        block_def.body = '{"a": 1}'
        block_def.body_type = "json"
        block_def.auth_type = "bearer"
        block_def.auth_config = {"token": "tk"}
        block_def.timeout_seconds = 60
        block_def.retry_count = 3
        block_def.retry_backoff = 2.0
        block_def.expected_status_codes = [200]
        block_def.allow_private_ips = False

        builder = BLOCK_TYPE_REGISTRY["http_request"]
        result = builder("my_http_block", block_def, {}, MagicMock(), {})

        assert isinstance(result, HttpRequestBlock)
        assert result.block_id == "my_http_block"

    def test_builder_passes_config_values(self):
        """The built HttpRequestBlock must carry all config values from the BlockDef."""
        HttpRequestBlock = _import_http_request_block()
        block_def = MagicMock()
        block_def.type = "http_request"
        block_def.url = "https://api.example.com/endpoint"
        block_def.method = "PUT"
        block_def.headers = {"Accept": "application/json"}
        block_def.body = "raw body"
        block_def.body_type = "raw"
        block_def.auth_type = "api_key"
        block_def.auth_config = {"header": "X-API-Key", "value": "secret"}
        block_def.timeout_seconds = 120
        block_def.retry_count = 2
        block_def.retry_backoff = 1.5
        block_def.expected_status_codes = [200, 204]
        block_def.allow_private_ips = True

        builder = BLOCK_TYPE_REGISTRY["http_request"]
        result = builder("cfg_block", block_def, {}, MagicMock(), {})

        assert isinstance(result, HttpRequestBlock)
        assert result.url == "https://api.example.com/endpoint"
        assert result.method == "PUT"
        assert result.headers == {"Accept": "application/json"}
        assert result.body == "raw body"
        assert result.body_type == "raw"
        assert result.auth_type == "api_key"
        assert result.auth_config == {"header": "X-API-Key", "value": "secret"}
        assert result.timeout_seconds == 120
        assert result.retry_count == 2
        assert result.retry_backoff == 1.5
        assert result.expected_status_codes == [200, 204]
        assert result.allow_private_ips is True

    def test_parsed_http_block_is_instance(self):
        """parse_workflow_yaml with type: http_request must produce an HttpRequestBlock."""
        HttpRequestBlock = _import_http_request_block()
        wf = parse_workflow_yaml(VALID_HTTP_REQUEST_YAML)
        block = wf.blocks.get("fetch_data")
        assert block is not None
        assert isinstance(block, HttpRequestBlock)

    def test_parsed_http_block_has_correct_url(self):
        """The parsed HttpRequestBlock must have the correct url from YAML."""
        _import_http_request_block()  # Ensure module exists
        wf = parse_workflow_yaml(VALID_HTTP_REQUEST_YAML)
        block = wf.blocks["fetch_data"]
        assert hasattr(block, "url")
        assert block.url == "https://api.example.com/v1/data"

    def test_parsed_http_block_has_correct_method(self):
        """The parsed HttpRequestBlock must have the correct method from YAML."""
        _import_http_request_block()  # Ensure module exists
        wf = parse_workflow_yaml(VALID_HTTP_REQUEST_YAML)
        block = wf.blocks["fetch_data"]
        assert hasattr(block, "method")
        assert block.method == "POST"


# ===========================================================================
# 12. JSON schema generation — HttpRequestBlockDef appears
# ===========================================================================


class TestHttpRequestJsonSchema:
    def test_http_request_in_json_schema(self):
        """HttpRequestBlockDef must appear in the generated JSON schema."""
        _import_http_request_block_def()  # Ensure the model exists
        schema = RunsightWorkflowFile.model_json_schema()
        schema_str = json.dumps(schema)
        assert "HttpRequestBlockDef" in schema_str

    def test_http_request_type_discriminator_in_schema(self):
        """'http_request' must appear as a valid discriminator value in the JSON schema."""
        _import_http_request_block_def()  # Ensure the model exists
        schema = RunsightWorkflowFile.model_json_schema()
        schema_str = json.dumps(schema)
        assert "http_request" in schema_str

    def test_http_request_url_field_in_schema(self):
        """The 'url' field must appear in the HttpRequestBlockDef schema definition."""
        _import_http_request_block_def()  # Ensure the model exists
        schema = RunsightWorkflowFile.model_json_schema()
        defs = schema.get("$defs", {})
        http_def = defs.get("HttpRequestBlockDef", {})
        properties = http_def.get("properties", {})
        assert "url" in properties, (
            f"Expected 'url' in HttpRequestBlockDef properties. "
            f"Available $defs: {list(defs.keys())}"
        )
