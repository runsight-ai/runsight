import { describe, expect, it } from "vitest";

import { parseWorkflowYamlToGraph } from "../yamlParser";

describe("HTTP request YAML parser", () => {
  it("maps snake_case HTTP fields to camelCase node data", () => {
    const yamlText = `
version: "1.0"
blocks:
  api_call:
    type: http_request
    url: https://api.example.test
    method: POST
    headers:
      Content-Type: application/json
    body: '{"key": "value"}'
    body_type: json
    auth_type: bearer
    auth_config:
      token: parser_dummy_token
    timeout_seconds: 30
    retry_count: 3
    retry_backoff: exponential
    expected_status_codes:
      - 200
      - 201
    allow_private_ips: false
workflow:
  name: Workflow
  entry: api_call
  transitions: []
`;

    const result = parseWorkflowYamlToGraph(yamlText);
    const data = result.nodes.find((node) => node.id === "api_call")?.data;

    expect(result.error).toBeUndefined();
    expect(data).toEqual(
      expect.objectContaining({
        stepType: "http_request",
        url: "https://api.example.test",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: '{"key": "value"}',
        bodyType: "json",
        authType: "bearer",
        authConfig: { token: "parser_dummy_token" },
        timeoutSeconds: 30,
        retryCount: 3,
        retryBackoff: "exponential",
        expectedStatusCodes: [200, 201],
        allowPrivateIps: false,
      }),
    );
  });

  it("parses a minimal http_request block without adding optional fields", () => {
    const yamlText = `
version: "1.0"
blocks:
  simple_get:
    type: http_request
    url: https://api.example.test/get
workflow:
  name: Workflow
  entry: simple_get
  transitions: []
`;

    const result = parseWorkflowYamlToGraph(yamlText);
    const data = result.nodes.find((node) => node.id === "simple_get")?.data;

    expect(result.error).toBeUndefined();
    expect(data).toEqual(
      expect.objectContaining({
        stepType: "http_request",
        url: "https://api.example.test/get",
      }),
    );
    expect(data).not.toHaveProperty("method");
    expect(data).not.toHaveProperty("bodyType");
  });
});
