import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

describe("editor type surface contract", () => {
  const source = readFileSync(
    resolve(__dirname, "../../../types/schemas/canvas.ts"),
    "utf-8",
  );

  it("exposes dispatch block fields in editor and workflow block types", () => {
    expect(source).toMatch(/\|\s*"dispatch"/);
    expect(source).toMatch(/\bsoulRefs\?\s*:\s*string\[\]/);
    expect(source).toMatch(/\bsoul_refs\?\s*:\s*string\[\]/);
  });
});
