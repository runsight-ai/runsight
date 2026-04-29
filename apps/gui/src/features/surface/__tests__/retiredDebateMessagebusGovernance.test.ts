/**
 * Governance: retired debate and message_bus surface boundary.
 *
 * Owner: GUI Surface YAML parser/compiler.
 * Boundary: retired debate/message_bus block types and their old frontend-only
 * fields must not re-enter surface source as typed schema, palette, parser, or
 * compiler special cases. Generic unknown block round-tripping is owned by
 * genericBlockRoundTrip.test.ts.
 * Exit criteria: remove once retired block-type denial is generated from a
 * shared block registry.
 */

import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const GUI_SRC_DIR = resolve(__dirname, "../../..");

function rgSurfaceSource(pattern: string): string {
  try {
    const output = execFileSync(
      "rg",
      [
        "-n",
        "--glob",
        "!__tests__/**",
        "--glob",
        "!**/__tests__/**",
        "--glob",
        "!*.test.ts",
        "--glob",
        "!*.test.tsx",
        "--glob",
        "*.{ts,tsx}",
        pattern,
        resolve(GUI_SRC_DIR, "features/surface"),
        resolve(GUI_SRC_DIR, "types/schemas/canvas.ts"),
      ],
      { encoding: "utf-8" },
    );

    return output
      .split("\n")
      .filter((line) => !line.includes("/__tests__/"))
      .join("\n")
      .trim();
  } catch (error) {
    const status = (error as { status?: number }).status;
    if (status === 1) {
      return "";
    }

    throw error;
  }
}

describe("Governance: retired debate and message_bus surface boundary", () => {
  it("keeps retired block type names out of surface source", () => {
    expect(rgSurfaceSource(String.raw`\b(?:debate|message_bus)\b`)).toBe("");
  });

  it("keeps retired debate field names out of typed surface source", () => {
    expect(
      rgSurfaceSource(
        String.raw`\b(?:soulARef|soulBRef|soul_a_ref|soul_b_ref|iterations)\b`,
      ),
    ).toBe("");
  });
});
