import { describe, expect, it } from "vitest";

import {
  compileOne,
  makeYaml,
  mockNode,
  parseFirst,
  roundTrip,
} from "./helpers/genericBlockRoundTripHelpers";

describe("Known nested object fields still work after generic changes", () => {
  it("carry_context still gets key conversion on parse", () => {
    const yaml = makeYaml({
      step1: {
        type: "loop",
        inner_block_refs: ["step_a"],
        carry_context: {
          enabled: true,
          mode: "last",
          source_blocks: ["step_a"],
          inject_as: "previous_output",
        },
      },
    });
    const data = parseFirst(yaml);

    expect(data.carryContext).toEqual({
      enabled: true,
      mode: "last",
      sourceBlocks: ["step_a"],
      injectAs: "previous_output",
    });
  });

  it("retry_config still gets key conversion on parse", () => {
    const yaml = makeYaml({
      step1: {
        type: "linear",
        soul_ref: "analyst",
        retry_config: {
          max_attempts: 3,
          backoff: "exponential",
          backoff_base_seconds: 2,
        },
      },
    });
    const data = parseFirst(yaml);

    expect(data.retryConfig).toEqual({
      maxAttempts: 3,
      backoff: "exponential",
      backoffBaseSeconds: 2,
    });
  });

  it("carry_context still gets key conversion on compile", () => {
    const node = mockNode("step1", "loop", {
      innerBlockRefs: ["step_a"],
      carryContext: {
        enabled: true,
        mode: "last",
        sourceBlocks: ["step_a"],
        injectAs: "previous_output",
      },
    });

    const { block } = compileOne(node);

    expect(block.carry_context).toEqual({
      enabled: true,
      mode: "last",
      source_blocks: ["step_a"],
      inject_as: "previous_output",
    });
  });

  it("loop with break_condition round-trips correctly", () => {
    const node = mockNode("step1", "loop", {
      innerBlockRefs: ["step_a", "step_b"],
      maxRounds: 5,
      breakCondition: "result.converged == true",
    });

    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });

    expect(doc2.blocks["step1"]).toEqual(doc1.blocks["step1"]);
  });
});

describe("Existing known types unaffected by generic changes", () => {
  it("linear block still round-trips", () => {
    const node = mockNode("b1", "linear", { soulRef: "analyst" });
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });
    expect(doc2.blocks["b1"]).toEqual(doc1.blocks["b1"]);
  });

  it("code block still round-trips", () => {
    const node = mockNode("b1", "code", {
      code: "print('hello')",
      timeoutSeconds: 60,
      allowedImports: ["json", "math"],
    });
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });
    expect(doc2.blocks["b1"]).toEqual(doc1.blocks["b1"]);
  });

  it("loop block still round-trips", () => {
    const node = mockNode("b1", "loop", {
      innerBlockRefs: ["step_a"],
      maxRounds: 5,
      breakCondition: "result.done == true",
      carryContext: {
        enabled: true,
        mode: "all",
        sourceBlocks: ["step_a"],
        injectAs: "prior",
      },
    });
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });
    expect(doc2.blocks["b1"]).toEqual(doc1.blocks["b1"]);
  });

  it("gate block still round-trips", () => {
    const node = mockNode("b1", "gate", {
      soulRef: "gatekeeper",
      evalKey: "quality",
      extractField: "score",
    });
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });
    expect(doc2.blocks["b1"]).toEqual(doc1.blocks["b1"]);
  });

  it("http_request block still round-trips", () => {
    const node = mockNode("b1", "http_request", {
      url: "https://api.example.test",
      method: "POST",
      bodyType: "json",
      timeoutSeconds: 30,
      expectedStatusCodes: [200, 201],
    });
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });
    expect(doc2.blocks["b1"]).toEqual(doc1.blocks["b1"]);
  });
});
