// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";

describe("SurfaceRunInputsCell import safety", () => {
  afterEach(() => {
    vi.resetModules();
    vi.unstubAllGlobals();
  });

  it("imports SurfaceRunInputsCell when navigator is missing", async () => {
    vi.resetModules();
    vi.stubGlobal("navigator", undefined);

    await expect(import("../SurfaceRunInputsCell")).resolves.toHaveProperty(
      "SurfaceRunInputsCell",
    );
  });
});
