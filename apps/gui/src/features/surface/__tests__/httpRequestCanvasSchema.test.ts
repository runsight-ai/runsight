import { describe, expect, it } from "vitest";

import type { BlockDef, StepNodeData, StepType } from "../../../types/schemas/canvas";
import { mockNode } from "./yamlTestBuilders";

describe("HTTP request canvas schema", () => {
  it("accepts http_request as a step type with camelCase node fields", () => {
    const node = mockNode("http_block", "http_request" as StepType, {
      url: "https://api.example.test/data",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: '{"key": "value"}',
      bodyType: "json",
      authType: "bearer",
      authConfig: { token: "abc123" },
      timeoutSeconds: 30,
      retryCount: 3,
      retryBackoff: "exponential",
      expectedStatusCodes: [200, 201],
      allowPrivateIps: false,
    } as Partial<StepNodeData>);

    expect(node.data.stepType).toBe("http_request");
    expect(node.data.url).toBe("https://api.example.test/data");
    expect(node.data.bodyType).toBe("json");
    expect(node.data.authType).toBe("bearer");
    expect(node.data.retryCount).toBe(3);
    expect(node.data.expectedStatusCodes).toEqual([200, 201]);
    expect(node.data.allowPrivateIps).toBe(false);
  });

  it("accepts http_request block definitions with snake_case transport fields", () => {
    const block: BlockDef = {
      type: "http_request" as StepType,
      url: "https://api.example.test",
      method: "GET",
      headers: { Authorization: "Bearer token" },
      body: "{}",
      body_type: "json",
      auth_type: "bearer",
      auth_config: { token: "abc" },
      timeout_seconds: 30,
      retry_count: 3,
      retry_backoff: "exponential",
      expected_status_codes: [200],
      allow_private_ips: false,
    } as BlockDef;

    expect(block.type).toBe("http_request");
    expect(block.url).toBe("https://api.example.test");
    expect(block.body_type).toBe("json");
    expect(block.retry_count).toBe(3);
    expect(block.expected_status_codes).toEqual([200]);
  });
});
