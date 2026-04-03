/**
 * RED-TEAM tests for RUN-575: Align default workflow template with library-only souls.
 *
 * After RUN-570 killed inline souls in the schema, the default template YAML
 * (TEMPLATE_YAML in features/setup/constants.ts) must be updated:
 *   - AC1: No `souls:` section in the template
 *   - AC2: `soul_ref` values still reference researcher, writer, reviewer
 *          (now resolved from custom/souls/ library files, not inline)
 *
 * All tests should FAIL until the template constant is rewritten.
 */

import { describe, it, expect } from "vitest";
import { TEMPLATE_YAML } from "../constants";

// ---------------------------------------------------------------------------
// AC1: TEMPLATE_YAML must NOT contain a `souls:` section
// ---------------------------------------------------------------------------

describe("RUN-575 AC1: template has no inline souls section", () => {
  it("does not contain a top-level souls: key", () => {
    // A top-level `souls:` key means inline soul definitions are still present.
    // After RUN-575, the template should have NO `souls:` section at all.
    const hasSoulsSection = /^souls:/m.test(TEMPLATE_YAML);
    expect(hasSoulsSection).toBe(false);
  });

  it("does not contain any system_prompt fields (inline soul artifact)", () => {
    // system_prompt is a field inside inline soul definitions.
    // If the template still has system_prompt, it still has inline souls.
    expect(TEMPLATE_YAML).not.toMatch(/system_prompt:/);
  });

  it("does not contain any role fields under a souls section", () => {
    // role: is another inline-soul field that should disappear
    // when the souls: section is removed. We check specifically for
    // the pattern of `role:` indented under what would be a soul definition.
    expect(TEMPLATE_YAML).not.toMatch(/^\s+role:\s+/m);
  });
});

// ---------------------------------------------------------------------------
// AC2: TEMPLATE_YAML still uses soul_ref for researcher, writer, reviewer
// ---------------------------------------------------------------------------

describe("RUN-575 AC2: template soul_ref values point to library souls", () => {
  it("has soul_ref: researcher in the research block", () => {
    // The research block must still reference the researcher soul via soul_ref.
    // After the migration, this resolves against custom/souls/researcher.yaml.
    expect(TEMPLATE_YAML).toMatch(/soul_ref:\s*researcher/);
  });

  it("has soul_ref: writer in the write_summary block", () => {
    expect(TEMPLATE_YAML).toMatch(/soul_ref:\s*writer/);
  });

  it("has soul_ref: reviewer in the quality_review block", () => {
    expect(TEMPLATE_YAML).toMatch(/soul_ref:\s*reviewer/);
  });

  it("contains exactly 3 soul_ref declarations", () => {
    const soulRefMatches = TEMPLATE_YAML.match(/soul_ref:/g) ?? [];
    expect(soulRefMatches).toHaveLength(3);
  });
});
