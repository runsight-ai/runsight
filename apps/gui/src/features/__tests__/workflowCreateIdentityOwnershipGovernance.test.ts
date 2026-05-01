/**
 * Governance: workflow-create identity test ownership boundary.
 *
 * Owner: GUI setup/workflow draft helper contract.
 * Boundary: embedded workflow YAML identity is asserted in one setup-owned
 * helper contract suite. Dashboard and Flows creation tests may assert the
 * interaction and result-based navigation, but they must not duplicate YAML
 * document internals such as id, kind, or untitled fallback checks.
 * Exit criteria: remove this governance suite once the workflow-create draft
 * helper contract is the stable shared test owner and duplicate page-level
 * YAML-internal assertions cannot be reintroduced by local test patterns.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const FEATURES_DIR = resolve(__dirname, "..");

const WORKFLOW_CREATE_TESTS = [
  {
    label: "Flows workflow-create interaction test",
    role: "consumer",
    relativePath: "flows/__tests__/workflowCreateIdentity.test.ts",
  },
  {
    label: "Dashboard workflow-create interaction test",
    role: "consumer",
    relativePath: "dashboard/__tests__/dashboardWorkflowCreateIdentity.test.ts",
  },
  {
    label: "Setup workflow draft helper contract",
    role: "owner",
    relativePath: "setup/__tests__/workflowCreateIdentity.test.tsx",
  },
] as const;

function readFeatureTest(relativePath: string): string {
  return readFileSync(resolve(FEATURES_DIR, relativePath), "utf-8");
}

function yamlInternalAssertionTerms(source: string): string[] {
  const terms: Array<{ label: string; pattern: RegExp }> = [
    { label: "YAML parser import", pattern: /from\s+["']yaml["']/ },
    { label: "YAML parse", pattern: /\bparse\(/ },
    { label: "payload.yaml inspection", pattern: /\.yaml\b/ },
    {
      label: "parsed YAML document variable",
      pattern: /\b(?:parsed|firstDoc|secondDoc|firstYaml|secondYaml)\b/,
    },
    { label: "workflow kind field", pattern: /\.kind\b|["']kind["']\s*:/ },
    { label: "untitled fallback id", pattern: /untitled-workflow/ },
    {
      label: "YAML contains embedded id",
      pattern: /\.toContain\s*\(\s*String\s*\([^)]*\.id\b/,
    },
  ];

  return terms
    .filter((term) => term.pattern.test(source))
    .map((term) => term.label);
}

function setupOwnerContractGaps(source: string): string[] {
  const contractAssertions: Array<{ label: string; pattern: RegExp }> = [
    {
      label: "parses buildBlankWorkflowYaml output",
      pattern: /\bparse\s*\([^)]*(?:yaml|buildBlankWorkflowYaml)/,
    },
    {
      label: "asserts serialized id",
      pattern: /expect\([^)]*\.id\)\.toBe\(/,
    },
    {
      label: 'asserts kind: "workflow"',
      pattern: /expect\([^)]*\.kind\)\.toBe\(["']workflow["']\)/,
    },
    {
      label: "asserts YAML embeds the generated id",
      pattern:
        /expect\([^)]*yaml[^)]*\)\.toContain\s*\([^)]*(?:\.id\b|workflowId|WorkflowId)/,
    },
    {
      label: "asserts created draft ids are not untitled-workflow",
      pattern: /\.not\.to(?:Be|Contain)\(["']untitled-workflow["']\)/,
    },
    {
      label: "asserts multiple draft/create identities are unique",
      pattern:
        /\.not\.toEqual\([^)]*(?:\.id\b|workflowId|WorkflowId)|new Set\([^)]*\)\.size|toHaveLength\(2\)[\s\S]*\.not\.toEqual\(/,
    },
  ];

  return contractAssertions
    .filter((assertion) => !assertion.pattern.test(source))
    .map((assertion) => assertion.label);
}

function setupSourceStringGaps(source: string): string[] {
  const sourceStringChecks: Array<{ label: string; pattern: RegExp }> = [
    {
      label: "remove readFileSync/readSetupStartPageSource source reads",
      pattern: /\breadFileSync\b|readSetupStartPageSource/,
    },
    {
      label: "remove SetupStartPage.tsx implementation source references",
      pattern: /SetupStartPage\.tsx/,
    },
    {
      label: "remove implementation-string toContain assertions",
      pattern:
        /\.toContain\(["'`][^"'`]*(workflowIdTouched|navigate\(|workflow-id)/,
    },
  ];

  return sourceStringChecks
    .filter((check) => check.pattern.test(source))
    .map((check) => check.label);
}

describe("Governance: workflow-create identity test ownership", () => {
  it("requires the setup workflow draft helper contract to own full YAML identity behavior", () => {
    const source = readFeatureTest(
      "setup/__tests__/workflowCreateIdentity.test.tsx",
    );
    const missingContractAssertions = setupOwnerContractGaps(source);

    expect(
      missingContractAssertions,
      [
        "The setup-owned helper contract must verify workflow draft identity internals:",
        'id, kind: "workflow", embedded id containment, non-untitled create ids,',
        "and uniqueness across multiple draft/create identities.",
      ].join(" "),
    ).toEqual([]);
  });

  it("keeps Dashboard and Flows tests focused on creation interaction and navigation", () => {
    const consumerLeaks = WORKFLOW_CREATE_TESTS.filter(
      (testFile) => testFile.role === "consumer",
    ).flatMap((testFile) => {
      const source = readFeatureTest(testFile.relativePath);
      const leakedTerms = yamlInternalAssertionTerms(source);
      return leakedTerms.length > 0
        ? [`${testFile.label}: ${leakedTerms.join(", ")}`]
        : [];
    });

    expect(
      consumerLeaks,
      "Dashboard and Flows should keep interaction/navigation coverage and delegate YAML internals to the setup helper contract",
    ).toEqual([]);
  });

  it("reframes setup source-text wiring checks into helper contract behavior", () => {
    const source = readFeatureTest(
      "setup/__tests__/workflowCreateIdentity.test.tsx",
    );
    const reframingGaps = [
      ...setupOwnerContractGaps(source).map(
        (gap) => `missing helper contract: ${gap}`,
      ),
      ...setupSourceStringGaps(source),
    ];

    expect(
      reframingGaps,
      "Removing SetupStartPage source-string assertions is only acceptable when the setup helper contract covers YAML identity behavior explicitly",
    ).toEqual([]);
  });
});
