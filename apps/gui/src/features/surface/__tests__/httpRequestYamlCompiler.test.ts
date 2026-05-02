import { describe, expect, it } from "vitest";

import { compileGraphToWorkflowYaml } from "../yamlCompiler";
import type { StepNodeData, StepType } from "../../../types/schemas/canvas";
import { mockNode } from "./yamlTestBuilders";

describe("HTTP request YAML compiler", () => {
  it("compiles http_request nodes with all HTTP fields in snake_case", () => {
    const node = mockNode("full_http", "http_request" as StepType, {
      url: "https://api.example.test/submit",
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Api-Key": "key123" },
      body: '{"payload": true}',
      bodyType: "json",
      authType: "bearer",
      authConfig: { token: "secret" },
      timeoutSeconds: 60,
      retryCount: 5,
      retryBackoff: "exponential",
      expectedStatusCodes: [200, 201, 204],
      allowPrivateIps: true,
    } as Partial<StepNodeData>);

    const { workflowDocument: doc, yaml } = compileGraphToWorkflowYaml({
      nodes: [node],
      edges: [],
    });

    const block = doc.blocks["full_http"] as Record<string, unknown>;
    expect(block).toEqual(
      expect.objectContaining({
        type: "http_request",
        url: "https://api.example.test/submit",
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Api-Key": "key123" },
        body: '{"payload": true}',
        body_type: "json",
        auth_type: "bearer",
        auth_config: { token: "secret" },
        timeout_seconds: 60,
        retry_count: 5,
        retry_backoff: "exponential",
        expected_status_codes: [200, 201, 204],
        allow_private_ips: true,
      }),
    );
    expect(yaml).toContain("type: http_request");
    expect(yaml).toContain("body_type:");
    expect(yaml).toContain("auth_type:");
    expect(yaml).toContain("timeout_seconds:");
    expect(yaml).toContain("expected_status_codes:");
    expect(yaml).not.toContain("bodyType:");
    expect(yaml).not.toContain("expectedStatusCodes:");
  });

  it("omits unset HTTP fields from minimal http_request blocks", () => {
    const node = mockNode("minimal_http", "http_request" as StepType, {
      url: "https://api.example.test",
    } as Partial<StepNodeData>);

    const { workflowDocument: doc } = compileGraphToWorkflowYaml({
      nodes: [node],
      edges: [],
    });

    const block = doc.blocks["minimal_http"] as Record<string, unknown>;
    expect(block).toEqual({
      type: "http_request",
      url: "https://api.example.test",
    });
  });
});
