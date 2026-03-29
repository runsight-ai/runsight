/**
 * RED-TEAM tests for RUN-216: HTTP block frontend sync.
 *
 * Validates:
 * - `http_request` exists in StepType union
 * - StepNodeData and BlockDef accept HTTP-specific fields
 * - Compiler emits `type: http_request` with all HTTP fields in snake_case
 * - Compiler omits undefined HTTP fields (no noise)
 * - Parser accepts `type: http_request` without error
 * - Parser maps snake_case HTTP fields to camelCase node data
 * - Round-trip: http_request nodes survive compile -> parse -> compile
 *
 * These tests MUST FAIL until the Green Team implements the feature.
 */

import { describe, it, expect } from "vitest";
import { compileGraphToWorkflowYaml } from "../yamlCompiler";
import { parseWorkflowYamlToGraph } from "../yamlParser";
import type { StepNodeData, StepType, BlockDef, SoulDef } from "../../../types/schemas/canvas";
import type { Node, Edge } from "@xyflow/react";

// ---------------------------------------------------------------------------
// Helpers (same pattern as yamlRoundTrip.test.ts / yamlStatefulField.test.ts)
// ---------------------------------------------------------------------------

function mockNode(
  id: string,
  stepType: StepType,
  extraData: Partial<StepNodeData> = {},
): Node<StepNodeData> {
  return {
    id,
    type: "canvasNode",
    position: { x: 0, y: 0 },
    data: {
      stepId: id,
      name: id,
      stepType,
      status: "idle",
      ...extraData,
    },
  };
}

function mockEdge(
  source: string,
  target: string,
  sourceHandle?: string,
): Edge {
  return {
    id: `${source}->${target}${sourceHandle ? `:${sourceHandle}` : ""}`,
    source,
    target,
    sourceHandle: sourceHandle ?? null,
    targetHandle: null,
  };
}

interface CompileInput {
  nodes: Node<StepNodeData>[];
  edges: Edge[];
  workflowName?: string;
  souls?: Record<string, SoulDef>;
  config?: Record<string, unknown>;
}

/**
 * Core round-trip: compile -> parse -> compile.
 * Returns both YAML strings and compiled documents for assertion.
 */
function roundTrip(input: CompileInput) {
  const { yaml: yaml1, workflowDocument: doc1 } = compileGraphToWorkflowYaml(input);
  const parsed = parseWorkflowYamlToGraph(yaml1);

  // Rebuild compile input from parsed result
  const input2: CompileInput = {
    nodes: parsed.nodes,
    edges: parsed.edges,
    souls: parsed.souls,
    config: parsed.config,
    workflowName: input.workflowName,
  };
  const { yaml: yaml2, workflowDocument: doc2 } = compileGraphToWorkflowYaml(input2);

  return { yaml1, yaml2, doc1, doc2, parsed };
}

// ===========================================================================
// 1. Type existence tests
// ===========================================================================

describe("Type existence: http_request", () => {
  it("StepType should accept 'http_request' as a valid value", () => {
    // This validates http_request is in the StepType union.
    // If it's missing, TypeScript compilation will fail on the mockNode call.
    const node = mockNode("http_block", "http_request" as StepType, {
      url: "https://api.example.com/data",
    } as Partial<StepNodeData>);

    expect(node.data.stepType).toBe("http_request");
  });

  it("StepNodeData should accept HTTP-specific fields without type errors", () => {
    const node = mockNode("http_block", "http_request" as StepType, {
      url: "https://api.example.com/data",
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

    expect(node.data.url).toBe("https://api.example.com/data");
    expect(node.data.method).toBe("POST");
    expect((node.data as Record<string, unknown>).bodyType).toBe("json");
    expect((node.data as Record<string, unknown>).authType).toBe("bearer");
    expect((node.data as Record<string, unknown>).retryCount).toBe(3);
    expect((node.data as Record<string, unknown>).retryBackoff).toBe("exponential");
    expect((node.data as Record<string, unknown>).expectedStatusCodes).toEqual([200, 201]);
    expect((node.data as Record<string, unknown>).allowPrivateIps).toBe(false);
  });

  it("BlockDef should accept HTTP-specific snake_case fields without type errors", () => {
    const block: BlockDef = {
      type: "http_request" as StepType,
      url: "https://api.example.com",
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
    expect((block as Record<string, unknown>).url).toBe("https://api.example.com");
    expect((block as Record<string, unknown>).body_type).toBe("json");
    expect((block as Record<string, unknown>).auth_type).toBe("bearer");
    expect((block as Record<string, unknown>).retry_count).toBe(3);
    expect((block as Record<string, unknown>).expected_status_codes).toEqual([200]);
  });
});

// ===========================================================================
// 2. Compiler tests
// ===========================================================================

describe("Compiler: http_request block", () => {
  it("compiles http_request node with url field", () => {
    const node = mockNode("api_call", "http_request" as StepType, {
      url: "https://api.example.com/data",
    } as Partial<StepNodeData>);

    const { workflowDocument: doc } = compileGraphToWorkflowYaml({
      nodes: [node],
      edges: [],
    });

    const block = doc.blocks["api_call"] as Record<string, unknown>;
    expect(block.type).toBe("http_request");
    expect(block.url).toBe("https://api.example.com/data");
  });

  it("emits 'type: http_request' in YAML output", () => {
    const node = mockNode("api_call", "http_request" as StepType, {
      url: "https://api.example.com/data",
    } as Partial<StepNodeData>);

    const { yaml } = compileGraphToWorkflowYaml({
      nodes: [node],
      edges: [],
    });

    expect(yaml).toContain("type: http_request");
    expect(yaml).toContain("url: https://api.example.com/data");
  });

  it("includes all http_request-specific fields when set", () => {
    const node = mockNode("full_http", "http_request" as StepType, {
      url: "https://api.example.com/submit",
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

    const { workflowDocument: doc } = compileGraphToWorkflowYaml({
      nodes: [node],
      edges: [],
    });

    const block = doc.blocks["full_http"] as Record<string, unknown>;
    expect(block.type).toBe("http_request");
    expect(block.url).toBe("https://api.example.com/submit");
    expect(block.method).toBe("POST");
    expect(block.headers).toEqual({ "Content-Type": "application/json", "X-Api-Key": "key123" });
    expect(block.body).toBe('{"payload": true}');
    expect(block.body_type).toBe("json");
    expect(block.auth_type).toBe("bearer");
    expect(block.auth_config).toEqual({ token: "secret" });
    expect(block.timeout_seconds).toBe(60);
    expect(block.retry_count).toBe(5);
    expect(block.retry_backoff).toBe("exponential");
    expect(block.expected_status_codes).toEqual([200, 201, 204]);
    expect(block.allow_private_ips).toBe(true);
  });

  it("omits undefined http_request fields (no noise)", () => {
    const node = mockNode("minimal_http", "http_request" as StepType, {
      url: "https://api.example.com",
    } as Partial<StepNodeData>);

    const { workflowDocument: doc } = compileGraphToWorkflowYaml({
      nodes: [node],
      edges: [],
    });

    const block = doc.blocks["minimal_http"] as Record<string, unknown>;
    expect(block.type).toBe("http_request");
    expect(block.url).toBe("https://api.example.com");
    // Fields not set should NOT appear
    expect(block).not.toHaveProperty("method");
    expect(block).not.toHaveProperty("headers");
    expect(block).not.toHaveProperty("body");
    expect(block).not.toHaveProperty("body_type");
    expect(block).not.toHaveProperty("auth_type");
    expect(block).not.toHaveProperty("auth_config");
    expect(block).not.toHaveProperty("retry_count");
    expect(block).not.toHaveProperty("retry_backoff");
    expect(block).not.toHaveProperty("expected_status_codes");
    expect(block).not.toHaveProperty("allow_private_ips");
  });

  it("camelCase fields convert to snake_case in compiled output", () => {
    const node = mockNode("snake_test", "http_request" as StepType, {
      url: "https://api.example.com",
      bodyType: "json",
      authType: "bearer",
      authConfig: { token: "t" },
      timeoutSeconds: 10,
      retryCount: 2,
      retryBackoff: "linear",
      expectedStatusCodes: [200],
      allowPrivateIps: false,
    } as Partial<StepNodeData>);

    const { workflowDocument: doc } = compileGraphToWorkflowYaml({
      nodes: [node],
      edges: [],
    });

    const block = doc.blocks["snake_test"] as Record<string, unknown>;

    // All should be snake_case keys in compiled output
    expect(block).toHaveProperty("body_type", "json");
    expect(block).toHaveProperty("auth_type", "bearer");
    expect(block).toHaveProperty("auth_config");
    expect(block).toHaveProperty("timeout_seconds", 10);
    expect(block).toHaveProperty("retry_count", 2);
    expect(block).toHaveProperty("retry_backoff", "linear");
    expect(block).toHaveProperty("expected_status_codes");
    expect(block).toHaveProperty("allow_private_ips", false);

    // camelCase keys should NOT appear
    expect(block).not.toHaveProperty("bodyType");
    expect(block).not.toHaveProperty("authType");
    expect(block).not.toHaveProperty("authConfig");
    expect(block).not.toHaveProperty("timeoutSeconds");
    expect(block).not.toHaveProperty("retryCount");
    expect(block).not.toHaveProperty("retryBackoff");
    expect(block).not.toHaveProperty("expectedStatusCodes");
    expect(block).not.toHaveProperty("allowPrivateIps");
  });

  it("snake_case field names appear in YAML string output", () => {
    const node = mockNode("yaml_snake", "http_request" as StepType, {
      url: "https://example.com",
      bodyType: "raw",
      authType: "api_key",
      timeoutSeconds: 15,
      retryCount: 1,
      retryBackoff: "fixed",
      expectedStatusCodes: [200],
      allowPrivateIps: true,
    } as Partial<StepNodeData>);

    const { yaml } = compileGraphToWorkflowYaml({
      nodes: [node],
      edges: [],
    });

    expect(yaml).toContain("body_type:");
    expect(yaml).toContain("auth_type:");
    expect(yaml).toContain("timeout_seconds:");
    expect(yaml).toContain("retry_count:");
    expect(yaml).toContain("retry_backoff:");
    expect(yaml).toContain("expected_status_codes:");
    expect(yaml).toContain("allow_private_ips:");

    // Should NOT contain camelCase keys
    expect(yaml).not.toContain("bodyType:");
    expect(yaml).not.toContain("authType:");
    expect(yaml).not.toContain("retryCount:");
    expect(yaml).not.toContain("retryBackoff:");
    expect(yaml).not.toContain("expectedStatusCodes:");
    expect(yaml).not.toContain("allowPrivateIps:");
  });
});

// ===========================================================================
// 3. Parser tests
// ===========================================================================

describe("Parser: http_request block", () => {
  it("parser accepts type: http_request without error", () => {
    const yamlText = `
version: "1.0"
blocks:
  api_call:
    type: http_request
    url: https://api.example.com/data
workflow:
  name: Workflow
  entry: api_call
  transitions: []
`;

    const result = parseWorkflowYamlToGraph(yamlText);
    const node = result.nodes.find((n) => n.id === "api_call");

    expect(node).toBeDefined();
    expect(node!.data.stepType).toBe("http_request");
    // Should not have an error about unknown block type
    expect(result.error).toBeUndefined();
  });

  it("parser maps snake_case fields to camelCase node data", () => {
    const yamlText = `
version: "1.0"
blocks:
  api_call:
    type: http_request
    url: https://api.example.com
    method: POST
    body: '{"key": "value"}'
    body_type: json
    auth_type: bearer
    auth_config:
      token: secret123
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
    const node = result.nodes.find((n) => n.id === "api_call");

    expect(node).toBeDefined();
    expect(node!.data.stepType).toBe("http_request");
    expect((node!.data as Record<string, unknown>).url).toBe("https://api.example.com");
    expect((node!.data as Record<string, unknown>).method).toBe("POST");
    expect((node!.data as Record<string, unknown>).body).toBe('{"key": "value"}');
    expect((node!.data as Record<string, unknown>).bodyType).toBe("json");
    expect((node!.data as Record<string, unknown>).authType).toBe("bearer");
    expect((node!.data as Record<string, unknown>).authConfig).toEqual({ token: "secret123" });
    expect(node!.data.timeoutSeconds).toBe(30);
    expect((node!.data as Record<string, unknown>).retryCount).toBe(3);
    expect((node!.data as Record<string, unknown>).retryBackoff).toBe("exponential");
    expect((node!.data as Record<string, unknown>).expectedStatusCodes).toEqual([200, 201]);
    expect((node!.data as Record<string, unknown>).allowPrivateIps).toBe(false);
  });

  it("parser preserves all http_request fields from YAML", () => {
    const yamlText = `
version: "1.0"
blocks:
  full_http:
    type: http_request
    url: https://api.example.com/submit
    method: PUT
    headers:
      Content-Type: application/json
      X-Custom: value
    body: '{"data": 42}'
    body_type: json
    auth_type: api_key
    auth_config:
      key: mykey
      header: X-Api-Key
    timeout_seconds: 45
    retry_count: 2
    retry_backoff: linear
    expected_status_codes:
      - 200
      - 204
    allow_private_ips: true
workflow:
  name: Workflow
  entry: full_http
  transitions: []
`;

    const result = parseWorkflowYamlToGraph(yamlText);
    const node = result.nodes.find((n) => n.id === "full_http");

    expect(node).toBeDefined();
    // Verify every field is preserved
    const data = node!.data as Record<string, unknown>;
    expect(data.url).toBe("https://api.example.com/submit");
    expect(data.method).toBe("PUT");
    expect(data.headers).toEqual({ "Content-Type": "application/json", "X-Custom": "value" });
    expect(data.body).toBe('{"data": 42}');
    expect(data.bodyType).toBe("json");
    expect(data.authType).toBe("api_key");
    expect(data.authConfig).toEqual({ key: "mykey", header: "X-Api-Key" });
    expect(node!.data.timeoutSeconds).toBe(45);
    expect(data.retryCount).toBe(2);
    expect(data.retryBackoff).toBe("linear");
    expect(data.expectedStatusCodes).toEqual([200, 204]);
    expect(data.allowPrivateIps).toBe(true);
  });

  it("parser handles minimal http_request block (only url)", () => {
    const yamlText = `
version: "1.0"
blocks:
  simple_get:
    type: http_request
    url: https://httpbin.org/get
workflow:
  name: Workflow
  entry: simple_get
  transitions: []
`;

    const result = parseWorkflowYamlToGraph(yamlText);
    const node = result.nodes.find((n) => n.id === "simple_get");

    expect(node).toBeDefined();
    expect(node!.data.stepType).toBe("http_request");
    expect((node!.data as Record<string, unknown>).url).toBe("https://httpbin.org/get");
    expect(result.error).toBeUndefined();
  });
});

// ===========================================================================
// 4. Round-trip tests
// ===========================================================================

describe("Round-trip: http_request block", () => {
  it("http_request node with all fields survives compile -> parse -> compile", () => {
    const node = mockNode("full_http", "http_request" as StepType, {
      url: "https://api.example.com/submit",
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer token" },
      body: '{"payload": true}',
      bodyType: "json",
      authType: "bearer",
      authConfig: { token: "secret" },
      timeoutSeconds: 60,
      retryCount: 5,
      retryBackoff: "exponential",
      expectedStatusCodes: [200, 201, 204],
      allowPrivateIps: false,
    } as Partial<StepNodeData>);

    const { doc1, doc2, yaml1, yaml2 } = roundTrip({ nodes: [node], edges: [] });

    // Block-level equality
    expect(doc2.blocks["full_http"]).toEqual(doc1.blocks["full_http"]);

    // Verify http_request type is preserved
    const block1 = doc1.blocks["full_http"] as Record<string, unknown>;
    const block2 = doc2.blocks["full_http"] as Record<string, unknown>;
    expect(block1.type).toBe("http_request");
    expect(block2.type).toBe("http_request");

    // Verify all fields survived
    expect(block1.url).toBe("https://api.example.com/submit");
    expect(block1.method).toBe("POST");
    expect(block1.body_type).toBe("json");
    expect(block1.auth_type).toBe("bearer");
    expect(block1.timeout_seconds).toBe(60);
    expect(block1.retry_count).toBe(5);
    expect(block1.retry_backoff).toBe("exponential");
    expect(block1.expected_status_codes).toEqual([200, 201, 204]);
    expect(block1.allow_private_ips).toBe(false);

    // YAML string equality
    expect(yaml2).toBe(yaml1);
  });

  it("http_request node with only url (minimal) survives round-trip", () => {
    const node = mockNode("simple_http", "http_request" as StepType, {
      url: "https://httpbin.org/get",
    } as Partial<StepNodeData>);

    const { doc1, doc2, yaml1, yaml2 } = roundTrip({ nodes: [node], edges: [] });

    expect(doc2.blocks["simple_http"]).toEqual(doc1.blocks["simple_http"]);

    const block1 = doc1.blocks["simple_http"] as Record<string, unknown>;
    expect(block1.type).toBe("http_request");
    expect(block1.url).toBe("https://httpbin.org/get");
    // Only type and url should be present
    expect(Object.keys(block1)).toEqual(expect.arrayContaining(["type", "url"]));

    expect(yaml2).toBe(yaml1);
  });

  it("mixed workflow with http_request + other block types round-trips correctly", () => {
    const souls: Record<string, SoulDef> = {
      planner: {
        id: "planner",
        role: "planner",
        system_prompt: "You plan tasks.",
        model_name: "claude-3-opus",
      },
    };

    const nodes = [
      mockNode("plan", "linear", { soulRef: "planner" }),
      mockNode("fetch_data", "http_request" as StepType, {
        url: "https://api.example.com/data",
        method: "GET",
        headers: { Accept: "application/json" },
        timeoutSeconds: 15,
        expectedStatusCodes: [200],
      } as Partial<StepNodeData>),
      mockNode("process", "code", {
        code: "result = data['items']",
        timeoutSeconds: 30,
        allowedImports: ["json"],
      }),
      mockNode("submit_result", "http_request" as StepType, {
        url: "https://api.example.com/results",
        method: "POST",
        bodyType: "json",
        authType: "bearer",
        authConfig: { token: "secret" },
        retryCount: 3,
        retryBackoff: "exponential",
      } as Partial<StepNodeData>),
    ];

    const edges = [
      mockEdge("plan", "fetch_data"),
      mockEdge("fetch_data", "process"),
      mockEdge("process", "submit_result"),
    ];

    const { doc1, doc2, yaml1, yaml2 } = roundTrip({
      nodes,
      edges,
      souls,
      workflowName: "http-pipeline",
    });

    // All blocks should survive
    expect(doc2.blocks).toEqual(doc1.blocks);

    // Verify http_request blocks specifically
    const fetchBlock = doc1.blocks["fetch_data"] as Record<string, unknown>;
    expect(fetchBlock.type).toBe("http_request");
    expect(fetchBlock.url).toBe("https://api.example.com/data");

    const submitBlock = doc1.blocks["submit_result"] as Record<string, unknown>;
    expect(submitBlock.type).toBe("http_request");
    expect(submitBlock.url).toBe("https://api.example.com/results");
    expect(submitBlock.body_type).toBe("json");

    // Transitions
    expect(doc2.workflow.transitions).toEqual(doc1.workflow.transitions);

    // Souls
    expect(doc2.souls).toEqual(doc1.souls);

    // YAML string equality
    expect(yaml2).toBe(yaml1);
  });

  it("http_request with universal fields (stateful, output_conditions) round-trips", () => {
    const node = mockNode("http_with_universal", "http_request" as StepType, {
      url: "https://api.example.com/check",
      method: "GET",
      expectedStatusCodes: [200, 404],
      stateful: true,
      outputConditions: [
        { case_id: "success", condition_group: { combinator: "and", conditions: [{ eval_key: "status", operator: "eq", value: 200 }] } },
        { case_id: "not_found", default: true },
      ],
    } as Partial<StepNodeData>);

    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });

    const block1 = doc1.blocks["http_with_universal"] as Record<string, unknown>;
    expect(block1.type).toBe("http_request");
    expect(block1.url).toBe("https://api.example.com/check");
    expect(block1.stateful).toBe(true);
    expect(block1.output_conditions).toBeDefined();
    expect(block1.expected_status_codes).toEqual([200, 404]);

    expect(doc2.blocks["http_with_universal"]).toEqual(doc1.blocks["http_with_universal"]);
  });
});

// ===========================================================================
// 5. Edge cases
// ===========================================================================

describe("Edge cases: http_request block", () => {
  it("http_request with empty headers object round-trips", () => {
    const node = mockNode("empty_headers", "http_request" as StepType, {
      url: "https://api.example.com",
      headers: {},
    } as Partial<StepNodeData>);

    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });

    expect(doc2.blocks["empty_headers"]).toEqual(doc1.blocks["empty_headers"]);
  });

  it("http_request with single expected status code round-trips", () => {
    const node = mockNode("single_status", "http_request" as StepType, {
      url: "https://api.example.com",
      expectedStatusCodes: [200],
    } as Partial<StepNodeData>);

    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });

    const block1 = doc1.blocks["single_status"] as Record<string, unknown>;
    expect(block1.expected_status_codes).toEqual([200]);
    expect(doc2.blocks["single_status"]).toEqual(doc1.blocks["single_status"]);
  });

  it("http_request combined with retry_config (universal) round-trips", () => {
    const node = mockNode("http_retry", "http_request" as StepType, {
      url: "https://api.example.com/flaky",
      method: "POST",
      retryCount: 3,
      retryBackoff: "exponential",
      retryConfig: {
        maxAttempts: 5,
        backoff: "exponential",
      },
    } as Partial<StepNodeData>);

    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });

    const block1 = doc1.blocks["http_retry"] as Record<string, unknown>;
    expect(block1.type).toBe("http_request");
    expect(block1.retry_count).toBe(3);
    expect(block1.retry_backoff).toBe("exponential");
    expect(block1).toHaveProperty("retry_config");
    expect(doc2.blocks["http_retry"]).toEqual(doc1.blocks["http_retry"]);
  });
});
