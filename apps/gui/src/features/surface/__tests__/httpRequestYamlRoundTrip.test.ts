import { describe, expect, it } from "vitest";

import type { StepNodeData, StepType } from "../../../types/schemas/canvas";
import { mockEdge, mockNode, roundTrip } from "./yamlTestBuilders";

describe("HTTP request YAML round trip", () => {
  it("preserves a full http_request block through compile, parse, and compile", () => {
    const node = mockNode("full_http", "http_request" as StepType, {
      url: "https://api.example.test/submit",
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

    expect(doc2.blocks["full_http"]).toEqual(doc1.blocks["full_http"]);
    expect(doc1.blocks["full_http"]).toEqual(
      expect.objectContaining({
        type: "http_request",
        url: "https://api.example.test/submit",
        body_type: "json",
        auth_type: "bearer",
        retry_count: 5,
        expected_status_codes: [200, 201, 204],
        allow_private_ips: false,
      }),
    );
    expect(yaml2).toBe(yaml1);
  });

  it("preserves minimal and edge-case HTTP fields", () => {
    const nodes = [
      mockNode("simple_http", "http_request" as StepType, {
        url: "https://api.example.test/get",
      } as Partial<StepNodeData>),
      mockNode("empty_headers", "http_request" as StepType, {
        url: "https://api.example.test/headers",
        headers: {},
      } as Partial<StepNodeData>),
      mockNode("single_status", "http_request" as StepType, {
        url: "https://api.example.test/status",
        expectedStatusCodes: [200],
      } as Partial<StepNodeData>),
    ];

    const { doc1, doc2, yaml1, yaml2 } = roundTrip({ nodes, edges: [] });

    expect(doc2.blocks).toEqual(doc1.blocks);
    expect(doc1.blocks["simple_http"]).toEqual({
      type: "http_request",
      url: "https://api.example.test/get",
    });
    expect((doc1.blocks["empty_headers"] as Record<string, unknown>).headers).toEqual({});
    expect((doc1.blocks["single_status"] as Record<string, unknown>).expected_status_codes).toEqual([200]);
    expect(yaml2).toBe(yaml1);
  });

  it("preserves HTTP blocks in mixed workflows with transitions and universal fields", () => {
    const nodes = [
      mockNode("plan", "linear", { soulRef: "planner" }),
      mockNode("fetch_data", "http_request" as StepType, {
        url: "https://api.example.test/data",
        method: "GET",
        expectedStatusCodes: [200],
        outputConditions: [
          {
            case_id: "success",
            condition_group: {
              combinator: "and",
              conditions: [{ eval_key: "status", operator: "eq", value: 200 }],
            },
          },
          { case_id: "not_found", default: true },
        ],
      } as Partial<StepNodeData>),
      mockNode("process", "code", {
        code: "result = data['items']",
        timeoutSeconds: 30,
        allowedImports: ["json"],
      }),
      mockNode("submit_result", "http_request" as StepType, {
        url: "https://api.example.test/results",
        method: "POST",
        retryCount: 3,
        retryBackoff: "exponential",
        retryConfig: {
          maxAttempts: 5,
          backoff: "exponential",
        },
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
      workflowName: "http-pipeline",
    });

    expect(doc2.blocks).toEqual(doc1.blocks);
    expect(doc2.workflow.transitions).toEqual(doc1.workflow.transitions);
    expect(doc1).not.toHaveProperty("souls");
    expect(doc2).not.toHaveProperty("souls");
    expect(doc1.blocks["fetch_data"]).toEqual(
      expect.objectContaining({
        type: "http_request",
        output_conditions: expect.any(Array),
      }),
    );
    expect(doc1.blocks["submit_result"]).toEqual(
      expect.objectContaining({
        type: "http_request",
        retry_config: expect.any(Object),
      }),
    );
    expect(yaml2).toBe(yaml1);
  });
});
