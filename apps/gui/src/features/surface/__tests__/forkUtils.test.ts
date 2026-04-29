import { afterEach, describe, expect, it, vi } from "vitest";

import { generateForkName, slugify } from "../forkUtils";

describe("fork workflow naming", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("slugifies workflow names for draft fork ids", () => {
    expect(slugify("Source Workflow: Release Digest!")).toBe(
      "source-workflow-release-digest",
    );
  });

  it("caps generated fork ids to the backend workflow id length limit", () => {
    vi.spyOn(Math, "random").mockReturnValue(0.123456789);
    const longName = `Source ${"workflow ".repeat(30)}`;

    const forkId = generateForkName(longName);

    expect(forkId).toMatch(/^drft-[a-z0-9-]+-[a-z0-9]{4}$/);
    expect(forkId).toContain("source-workflow");
    expect(forkId.length).toBeLessThanOrEqual(100);
  });
});
