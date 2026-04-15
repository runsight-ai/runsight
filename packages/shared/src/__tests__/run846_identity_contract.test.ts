import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  ProviderCreateSchema,
  SettingsProviderResponseSchema,
  SoulCreateSchema,
  WorkflowResponseSchema,
} from "../zod";

const API_TS_PATH = resolve(__dirname, "..", "api.ts");

function extractApiComponentFieldNames(source: string, componentName: string): string[] {
  const pattern = new RegExp(`${componentName}: \\{([\\s\\S]*?)\\n\\s+\\};`);
  const match = source.match(pattern);
  if (!match) {
    throw new Error(`Could not find ${componentName} component in generated api.ts output`);
  }

  return match[1]
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const fieldMatch = line.match(/^([A-Za-z0-9_]+)\??:/);
      return fieldMatch?.[1] ?? null;
    })
    .filter((field): field is string => field !== null);
}

describe("RUN-846 generated shared identity contracts", () => {
  it("committed ProviderCreateSchema requires embedded provider identity", () => {
    expect(ProviderCreateSchema.shape).toHaveProperty("id");
    expect(ProviderCreateSchema.shape).toHaveProperty("kind");
    expect(ProviderCreateSchema.shape).toHaveProperty("name");

    const valid = ProviderCreateSchema.safeParse({
      id: "openai",
      kind: "provider",
      name: "OpenAI",
      api_key_env: "sk-xxx",
      base_url: "https://api.openai.com/v1",
    });

    expect(valid.success).toBe(true);

    const missingKind = WorkflowResponseSchema.safeParse({
      id: "research-review",
      name: "Research Review",
    });

    expect(missingKind.success).toBe(false);
  });

  it("committed SoulCreateSchema requires embedded soul identity", () => {
    expect(SoulCreateSchema.shape).toHaveProperty("id");
    expect(SoulCreateSchema.shape).toHaveProperty("kind");
    expect(SoulCreateSchema.shape).toHaveProperty("name");
    expect(SoulCreateSchema.shape).toHaveProperty("role");
    expect(SoulCreateSchema.shape).toHaveProperty("system_prompt");

    const valid = SoulCreateSchema.safeParse({
      id: "researcher",
      kind: "soul",
      name: "Researcher",
      role: "Research File Writer",
      system_prompt: "Write a research brief.",
    });

    expect(valid.success).toBe(true);
  });

  it("committed WorkflowResponseSchema exposes embedded workflow identity", () => {
    expect(WorkflowResponseSchema.shape).toHaveProperty("id");
    expect(WorkflowResponseSchema.shape).toHaveProperty("kind");

    const valid = WorkflowResponseSchema.safeParse({
      id: "research-review",
      kind: "workflow",
      name: "Research Review",
      valid: true,
      enabled: true,
    });

    expect(valid.success).toBe(true);
  });

  it("committed SettingsProviderResponseSchema exposes embedded provider identity", () => {
    expect(SettingsProviderResponseSchema.shape).toHaveProperty("id");
    expect(SettingsProviderResponseSchema.shape).toHaveProperty("kind");

    const valid = SettingsProviderResponseSchema.safeParse({
      id: "openai",
      kind: "provider",
      name: "OpenAI",
      status: "connected",
      is_active: true,
    });

    expect(valid.success).toBe(true);
  });

  it("committed api.ts ProviderCreate component exposes embedded identity fields", () => {
    const apiSource = readFileSync(API_TS_PATH, "utf8");
    const fields = extractApiComponentFieldNames(apiSource, "ProviderCreate");

    expect(fields).toEqual(expect.arrayContaining(["id", "kind", "name"]));
  });

  it("committed api.ts WorkflowResponse component exposes embedded identity fields", () => {
    const apiSource = readFileSync(API_TS_PATH, "utf8");
    const fields = extractApiComponentFieldNames(apiSource, "WorkflowResponse");

    expect(fields).toEqual(expect.arrayContaining(["id", "kind"]));
  });

  it("committed api.ts SettingsProviderResponse component exposes embedded identity fields", () => {
    const apiSource = readFileSync(API_TS_PATH, "utf8");
    const fields = extractApiComponentFieldNames(apiSource, "SettingsProviderResponse");

    expect(fields).toEqual(expect.arrayContaining(["id", "kind"]));
  });

  it("committed api.ts SoulCreate component exposes embedded identity fields", () => {
    const apiSource = readFileSync(API_TS_PATH, "utf8");
    const fields = extractApiComponentFieldNames(apiSource, "SoulCreate");

    expect(fields).toEqual(expect.arrayContaining(["id", "kind", "name", "role", "system_prompt"]));
  });
});
