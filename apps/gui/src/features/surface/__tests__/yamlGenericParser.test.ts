import { describe, expect, it } from "vitest";

import { parseWorkflowYamlToGraph } from "../yamlParser";
import { makeYaml } from "./yamlTestBuilders";

describe("generic YAML parser known-type conversion", () => {
  it("parses linear soul_ref through generic camelCase conversion", () => {
    const result = parseWorkflowYamlToGraph(
      makeYaml({
        step1: { type: "linear", soul_ref: "analyst" },
      }),
    );

    expect(result.nodes[0]!.data.soulRef).toBe("analyst");
  });

  it("parses loop carry_context with recursive key conversion", () => {
    const result = parseWorkflowYamlToGraph(
      makeYaml({
        step1: {
          type: "loop",
          inner_block_refs: ["step_a"],
          max_rounds: 5,
          carry_context: {
            enabled: true,
            source_blocks: ["step_a"],
            inject_as: "prior",
          },
        },
      }),
    );
    const data = result.nodes[0]!.data;

    expect(data.innerBlockRefs).toEqual(["step_a"]);
    expect(data.maxRounds).toBe(5);
    expect(data.carryContext).toEqual({
      enabled: true,
      sourceBlocks: ["step_a"],
      injectAs: "prior",
    });
  });

  it("parses http_request snake_case fields and nested auth_config generically", () => {
    const result = parseWorkflowYamlToGraph(
      makeYaml({
        step1: {
          type: "http_request",
          url: "https://api.example.test",
          method: "POST",
          body_type: "json",
          auth_type: "bearer",
          auth_config: { token_env: "API_TOKEN" },
          timeout_seconds: 30,
          retry_count: 2,
          retry_backoff: "fixed",
          expected_status_codes: [200],
          allow_private_ips: false,
        },
      }),
    );
    const data = result.nodes[0]!.data;

    expect(data).toEqual(
      expect.objectContaining({
        url: "https://api.example.test",
        method: "POST",
        bodyType: "json",
        authType: "bearer",
        timeoutSeconds: 30,
        retryCount: 2,
        retryBackoff: "fixed",
        expectedStatusCodes: [200],
        allowPrivateIps: false,
      }),
    );
    expect(data.authConfig).toEqual({ tokenEnv: "API_TOKEN" });
  });
});
