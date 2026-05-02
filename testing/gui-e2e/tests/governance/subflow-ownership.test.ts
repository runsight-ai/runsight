/**
 * Governance coverage for subflow E2E ownership.
 *
 * These source-reading checks protect the E2E workspace from regressing to one
 * broad subflow spec that owns YAML fixtures, API helpers, and both success and
 * failure behavior. Delete this suite once the same boundaries are enforced by
 * lint rules or by stable E2E fixture conventions.
 */

import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const TESTS_DIR = resolve(__dirname, "..");
const HELPERS_DIR = resolve(TESTS_DIR, "helpers");

interface SpecSource {
  name: string;
  source: string;
}

function readFile(filePath: string): string {
  return readFileSync(filePath, "utf-8");
}

function readSubflowSpecs(): SpecSource[] {
  return readdirSync(TESTS_DIR)
    .filter((fileName) => /^subflows(?:[-\w]+)?\.spec\.ts$/.test(fileName))
    .map((fileName) => ({
      name: fileName,
      source: readFile(resolve(TESTS_DIR, fileName)),
    }));
}

function getSubflowHelperFiles(): string[] {
  return readdirSync(HELPERS_DIR).filter((fileName) =>
    /^subflow[\w-]*\.(?:ts|tsx)$/.test(fileName),
  );
}

function namesBehavior(name: string, behaviorNames: string[]): boolean {
  return behaviorNames.some((behaviorName) => name.includes(behaviorName));
}

function containsHappyPathOwnership(source: string): boolean {
  return /\bhappy\b|buildHappy|call_happy_child|completed/.test(source);
}

function containsFailurePathOwnership(source: string): boolean {
  return /\bfail(?:ed|ing|ure)?\b|buildFailing|call_failing_child/.test(source);
}

describe("Subflow E2E ownership governance", () => {
  it("keeps subflow YAML builders and API helpers in behavior-named helper files", () => {
    const helperFiles = getSubflowHelperFiles();

    expect(
      helperFiles.length,
      "Expected subflow fixture/helper ownership under tests/helpers, for example subflowFixtures.ts.",
    ).toBeGreaterThan(0);

    const helperSources = helperFiles
      .map((fileName) => readFile(resolve(HELPERS_DIR, fileName)))
      .join("\n");

    for (const expectedHelper of [
      "buildHappyChildYaml",
      "buildHappyParentYaml",
      "buildFailingChildYaml",
      "buildFailingParentYaml",
      "apiGet",
      "apiPost",
      "apiPut",
      "apiDelete",
      "waitForWorkflowRun",
      "waitForChildRun",
      "waitForRunNode",
    ]) {
      expect(
        helperSources,
        `${expectedHelper} should be owned by tests/helpers/subflowFixtures.ts or a behavior-named subflow helper.`,
      ).toContain(expectedHelper);
    }
  });

  it("splits the broad legacy subflow spec into behavior-named specs", () => {
    const specNames = readSubflowSpecs().map((spec) => spec.name);
    const hasHappySpec = specNames.some((name) =>
      namesBehavior(name, ["happy", "success", "completed"]),
    );
    const hasFailureSpec = specNames.some((name) =>
      namesBehavior(name, ["failure", "failing", "failed", "error"]),
    );

    expect(
      specNames,
      "Expected subflow E2E ownership to be split into behavior-named specs such as subflows-happy.spec.ts and subflows-failure.spec.ts.",
    ).not.toContain("subflows.spec.ts");
    expect(hasHappySpec, `Subflow specs found: ${specNames.join(", ")}`).toBe(true);
    expect(hasFailureSpec, `Subflow specs found: ${specNames.join(", ")}`).toBe(true);
  });

  it("keeps each subflow spec focused on either happy path or failure path behavior", () => {
    const mixedOwners = readSubflowSpecs()
      .filter(
        (spec) =>
          containsHappyPathOwnership(spec.source) &&
          containsFailurePathOwnership(spec.source),
      )
      .map((spec) => spec.name);

    expect(
      mixedOwners,
      "No single subflow spec should assert both happy/completed and failing/failed paths.",
    ).toEqual([]);
  });

  it("keeps every subflow spec free of inline fixture and API helper definitions", () => {
    const inlineDefinitions = readSubflowSpecs().flatMap((spec) => {
      const helperDefinitions = [
        "apiGet",
        "apiPost",
        "apiPut",
        "apiDelete",
        "buildHappyChildYaml",
        "buildHappyParentYaml",
        "buildFailingChildYaml",
        "buildFailingParentYaml",
      ].filter((functionName) =>
        new RegExp(`(?:async\\s+)?function\\s+${functionName}\\b`).test(
          spec.source,
        ),
      );

      return helperDefinitions.map(
        (functionName) => `${spec.name}: ${functionName}`,
      );
    });

    expect(
      inlineDefinitions,
      "Subflow specs must delegate API helpers and YAML builders to tests/helpers/subflowFixtures.ts or behavior-named subflow helpers.",
    ).toEqual([]);
  });
});
