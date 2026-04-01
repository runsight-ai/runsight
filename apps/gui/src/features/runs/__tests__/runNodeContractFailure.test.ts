import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
}));

vi.mock("../../../api/client", () => ({
  api: {
    get: mocks.apiGet,
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

const RUN_DETAIL_SOURCE = readFileSync(resolve(__dirname, "../RunDetail.tsx"), "utf-8");

beforeEach(() => {
  vi.resetModules();
  mocks.apiGet.mockReset();
});

describe("run-node adapter contract failures (RUN-498)", () => {
  it("rejects a non-array run-node payload instead of silently returning an empty graph", async () => {
    mocks.apiGet.mockResolvedValue({
      items: [],
    });

    const { runsApi } = await import("../../../api/runs");

    await expect(
      (runsApi as { getRunNodes: (id: string) => Promise<unknown> }).getRunNodes("run_1"),
    ).rejects.toThrow(/run.*node.*(contract|response)/i);
  });

  it("preserves backend failures distinctly from run-node contract failures", async () => {
    mocks.apiGet.mockRejectedValue(new Error("Nodes request failed"));

    const { runsApi } = await import("../../../api/runs");

    await expect(
      (runsApi as { getRunNodes: (id: string) => Promise<unknown> }).getRunNodes("run_1"),
    ).rejects.toThrow("Nodes request failed");
  });
});

describe("RunDetail contract-failure UI (RUN-498)", () => {
  it("reads explicit node-loading error state from useRunNodes instead of treating missing nodes as a blank graph", () => {
    expect(
      RUN_DETAIL_SOURCE,
      "Expected RunDetail to read an explicit error state from useRunNodes",
    ).toMatch(/useRunNodes\([^\n]+\)[\s\S]*?(isError|error|refetch)/);
  });

  it("renders a deliberate run-graph error state with retry guidance when node parsing fails", () => {
    const hasRunGraphErrorCopy =
      /run graph|load run graph|unable to load/i.test(RUN_DETAIL_SOURCE);
    const hasRetryGuidance = /retry|try again|refetch/i.test(RUN_DETAIL_SOURCE);

    expect(
      hasRunGraphErrorCopy && hasRetryGuidance,
      "Expected RunDetail to render visible run-graph error copy with retry guidance for contract failures",
    ).toBe(true);
  });
});
