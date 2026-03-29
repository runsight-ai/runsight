/**
 * RED-TEAM tests for RUN-353: Hello-world template "Research & Review" YAML.
 *
 * These tests verify the TEMPLATE_YAML constant exported from
 * features/setup/constants.ts. The constant should contain a valid
 * Runsight workflow YAML with:
 *   - 3 inline souls: researcher, writer, reviewer
 *   - 3 blocks: research (linear), write_summary (linear), quality_review (gate)
 *   - 2 transitions: research->write_summary, write_summary->quality_review
 *   - Gate block with eval_key pointing to writer output
 *
 * Expected failures: constants.ts does not exist yet, so the import will fail.
 */

import { describe, it, expect } from "vitest";

// This import will fail until the constant is implemented.
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-expect-error — module does not exist yet
import { TEMPLATE_YAML } from "../constants";

// ---------------------------------------------------------------------------
// 1. Export and basic shape
// ---------------------------------------------------------------------------

describe("TEMPLATE_YAML export", () => {
  it("is exported from features/setup/constants.ts", () => {
    expect(TEMPLATE_YAML).toBeDefined();
  });

  it("is a non-empty string", () => {
    expect(typeof TEMPLATE_YAML).toBe("string");
    expect(TEMPLATE_YAML.length).toBeGreaterThan(0);
  });

  it("contains version 1.0", () => {
    expect(TEMPLATE_YAML).toMatch(/version:\s*['"]?1\.0['"]?/);
  });
});

// ---------------------------------------------------------------------------
// 2. Soul definitions
// ---------------------------------------------------------------------------

describe("TEMPLATE_YAML soul definitions", () => {
  it("defines a researcher soul", () => {
    expect(TEMPLATE_YAML).toMatch(/souls:\s*\n(\s+.*\n)*?\s+researcher:/);
  });

  it("defines a writer soul", () => {
    expect(TEMPLATE_YAML).toMatch(/\bwriter:/);
  });

  it("defines a reviewer soul", () => {
    expect(TEMPLATE_YAML).toMatch(/\breviewer:/);
  });

  it("contains exactly 3 soul definitions under the souls key", () => {
    // Extract the souls section and count top-level keys
    const soulsMatch = TEMPLATE_YAML.match(
      /^souls:\s*\n((?:[ \t]+.*\n)*)/m,
    );
    expect(soulsMatch).not.toBeNull();
    const soulsBlock = soulsMatch![1];
    // Top-level soul keys are indented exactly 2 spaces
    const soulKeys = soulsBlock.match(/^ {2}\w+:/gm) ?? [];
    expect(soulKeys).toHaveLength(3);
  });
});

// ---------------------------------------------------------------------------
// 3. Block definitions
// ---------------------------------------------------------------------------

describe("TEMPLATE_YAML block definitions", () => {
  it("defines a research block", () => {
    expect(TEMPLATE_YAML).toMatch(/blocks:\s*\n(\s+.*\n)*?\s+research:/);
  });

  it("defines a write_summary block", () => {
    expect(TEMPLATE_YAML).toMatch(/\bwrite_summary:/);
  });

  it("defines a quality_review block", () => {
    expect(TEMPLATE_YAML).toMatch(/\bquality_review:/);
  });

  it("contains exactly 3 block definitions under the blocks key", () => {
    const blocksMatch = TEMPLATE_YAML.match(
      /^blocks:\s*\n((?:[ \t]+.*\n)*)/m,
    );
    expect(blocksMatch).not.toBeNull();
    const blocksBlock = blocksMatch![1];
    const blockKeys = blocksBlock.match(/^ {2}\w+:/gm) ?? [];
    expect(blockKeys).toHaveLength(3);
  });

  it("quality_review block has type: gate", () => {
    // After quality_review: there should be a type: gate within a few lines
    expect(TEMPLATE_YAML).toMatch(/quality_review:\s*\n\s+type:\s*gate/);
  });

  it("quality_review block has eval_key: write_summary", () => {
    expect(TEMPLATE_YAML).toMatch(/eval_key:\s*write_summary/);
  });

  it("quality_review block references reviewer soul", () => {
    expect(TEMPLATE_YAML).toMatch(
      /quality_review:\s*\n(?:\s+.*\n)*?\s+soul_ref:\s*reviewer/,
    );
  });
});

// ---------------------------------------------------------------------------
// 4. Workflow section
// ---------------------------------------------------------------------------

describe("TEMPLATE_YAML workflow section", () => {
  it("has entry: research", () => {
    expect(TEMPLATE_YAML).toMatch(/entry:\s*research/);
  });

  it("has a workflow name containing 'Research'", () => {
    expect(TEMPLATE_YAML).toMatch(/name:.*Research/);
  });

  it("has transition from research to write_summary", () => {
    expect(TEMPLATE_YAML).toMatch(
      /from:\s*research\s*\n\s+to:\s*write_summary/,
    );
  });

  it("has transition from write_summary to quality_review", () => {
    expect(TEMPLATE_YAML).toMatch(
      /from:\s*write_summary\s*\n\s+to:\s*quality_review/,
    );
  });

  it("has exactly 2 transitions", () => {
    const transitionMatches = TEMPLATE_YAML.match(/- from:/g) ?? [];
    expect(transitionMatches).toHaveLength(2);
  });
});
