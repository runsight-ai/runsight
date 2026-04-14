import { describe, expect, it } from "vitest";
import { parse } from "yaml";

import { TEMPLATE_YAML } from "../constants";

function parseTemplate(): Record<string, any> {
  return parse(TEMPLATE_YAML) as Record<string, any>;
}

describe("RUN-846 template identity contract", () => {
  it("embeds the workflow id and kind at the top level", () => {
    const parsed = parseTemplate();

    expect(parsed.id).toBe("research-review");
    expect(parsed.kind).toBe("workflow");
  });

  it("requires kind and name on the inline souls", () => {
    const parsed = parseTemplate();

    for (const soulKey of ["researcher", "reviewer", "error_writer"]) {
      expect(parsed.souls?.[soulKey]?.id).toBe(soulKey);
      expect(parsed.souls?.[soulKey]?.kind).toBe("soul");
      expect(typeof parsed.souls?.[soulKey]?.name).toBe("string");
      expect((parsed.souls?.[soulKey]?.name as string).length).toBeGreaterThan(0);
    }
  });

  it("still parses as valid workflow YAML", () => {
    const parsed = parseTemplate();

    expect(parsed.workflow?.entry).toBe("review_loop");
    expect(parsed.blocks).toBeDefined();
  });
});
