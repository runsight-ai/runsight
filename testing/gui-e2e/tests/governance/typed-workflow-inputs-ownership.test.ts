/**
 * Governance coverage for typed workflow input E2E ownership.
 *
 * Owner: testing/gui-e2e owns typed workflow input browser-flow behavior
 * assertions.
 * Boundary: workflow API helpers, run/rerun/detail helpers, clipboard capture,
 * validation interception, inline field assertions, and workflow YAML builders
 * belong in behavior-named helpers or fixtures, not in the Playwright spec.
 * Exit criteria: delete this suite once lint rules or stable E2E fixture
 * conventions enforce the same typed workflow input ownership boundary.
 */

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const TESTS_DIR = resolve(__dirname, "..");
const HELPERS_DIR = resolve(TESTS_DIR, "helpers");
const FIXTURES_DIR = resolve(TESTS_DIR, "fixtures");
const TYPED_WORKFLOW_INPUTS_SPEC = resolve(TESTS_DIR, "typed-workflow-inputs.spec.ts");

const TYPED_WORKFLOW_INPUT_HELPERS = [
  "createWorkflow",
  "deleteWorkflowIfPresent",
  "runWorkflowFromEditor",
  "clickRunButton",
  "currentRunId",
  "expectRunDetail",
  "expectNewRunDetail",
  "waitForRunSnapshot",
  "waitForNewestWorkflowRun",
  "workflowRunCount",
  "openRunsFooter",
  "openFirstRunInputDetails",
  "openFirstRerunModal",
  "expectNoVisibleSecret",
  "installClipboardCapture",
  "copiedText",
  "expectInlineFieldError",
  "interceptBackendConfigValidationError",
  "requiredStringWorkflowYaml",
  "dirtyRequiredWorkflowYaml",
  "noInputWorkflowYaml",
  "sensitiveWorkflowYaml",
] as const;

interface SourceFile {
  name: string;
  path: string;
  source: string;
}

function readFile(filePath: string): string {
  return readFileSync(filePath, "utf-8");
}

function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

function readTypedWorkflowInputsSpec(): string {
  return readFile(TYPED_WORKFLOW_INPUTS_SPEC);
}

function readTypedWorkflowInputFixtureFiles(): SourceFile[] {
  return [HELPERS_DIR, FIXTURES_DIR]
    .filter((dir) => existsSync(dir))
    .flatMap((dir) =>
      readdirSync(dir)
        .filter((fileName) => /typed[-_\w]*workflow[-_\w]*inputs/i.test(fileName))
        .filter((fileName) => /\.(?:ts|tsx)$/.test(fileName))
        .map((fileName) => {
          const path = resolve(dir, fileName);
          return {
            name: fileName,
            path,
            source: readFile(path),
          };
        }),
    );
}

function exportsNamedValue(source: string, valueName: string): boolean {
  const code = stripComments(source);
  return [
    `export\\s+(?:async\\s+)?function\\s+${valueName}\\b`,
    `export\\s+const\\s+${valueName}\\b`,
    `export\\s+type\\s+${valueName}\\b`,
    `export\\s+interface\\s+${valueName}\\b`,
    `export\\s*\\{[^}]*\\b${valueName}\\b[^}]*\\}`,
  ].some((pattern) => new RegExp(pattern).test(code));
}

function definesHelperInline(source: string, helperName: string): boolean {
  const code = stripComments(source);
  return [
    `(?:async\\s+)?function\\s+${helperName}\\b`,
    `(?:const|let|var)\\s+${helperName}\\s*=\\s*(?:async\\s*)?(?:\\([^)]*\\)|[\\w$]+)\\s*=>`,
    `(?:const|let|var)\\s+${helperName}\\s*=\\s*(?:async\\s+)?function\\b`,
  ].some((pattern) => new RegExp(pattern).test(code));
}

function containsAny(source: string, patterns: RegExp[]): boolean {
  return patterns.some((pattern) => pattern.test(source));
}

function countBehaviorAssertions(source: string): number {
  return (source.match(/\bexpect(?:\.poll)?\s*\(/g) ?? []).length;
}

describe("Typed workflow inputs E2E ownership governance", () => {
  it("keeps typed workflow input helpers and YAML builders in behavior-named helper files", () => {
    const fixtureFiles = readTypedWorkflowInputFixtureFiles();

    expect(
      fixtureFiles.map((file) => file.name),
      "Expected typed workflow input fixtures under tests/helpers or tests/fixtures, for example typed-workflow-inputs-fixture.ts.",
    ).not.toEqual([]);

    const helperSources = fixtureFiles.map((file) => file.source).join("\n");

    for (const expectedHelper of TYPED_WORKFLOW_INPUT_HELPERS) {
      expect(
        exportsNamedValue(helperSources, expectedHelper),
        `${expectedHelper} should be exported by a typed workflow input helper/fixture instead of owned by the spec.`,
      ).toBe(true);
    }
  });

  it("keeps the typed workflow inputs browser spec free of inline helper and YAML builder definitions", () => {
    const source = readTypedWorkflowInputsSpec();
    const inlineDefinitions = TYPED_WORKFLOW_INPUT_HELPERS.filter((helperName) =>
      definesHelperInline(source, helperName),
    );

    expect(
      inlineDefinitions,
      "typed-workflow-inputs.spec.ts should import API/run helpers, validation helpers, clipboard helpers, and YAML builders from a behavior-named typed workflow input helper/fixture.",
    ).toEqual([]);
  });

  it("keeps the spec attached to the typed workflow input fixture owner without banning helper calls", () => {
    const source = stripComments(readTypedWorkflowInputsSpec());

    expect(
      source,
      "The browser spec should import typed workflow input helpers from tests/helpers or tests/fixtures.",
    ).toMatch(
      /from\s+["']\.\/(?:helpers|fixtures)\/[^"']*typed[-_\w]*workflow[-_\w]*inputs[^"']*["']/i,
    );
  });

  it("preserves the four typed workflow input browser flows and their observable assertions", () => {
    const source = readTypedWorkflowInputsSpec();

    expect(
      containsAny(source, [
        /test\s*\(\s*["'`][^"'`]*required string input[^"'`]*modal[^"'`]*history[^"'`]*reruns/i,
        /test\s*\(\s*["'`][^"'`]*required[^"'`]*validates[^"'`]*history[^"'`]*prefill/i,
      ]),
      "Expected the required input modal/history/rerun prefill browser flow.",
    ).toBe(true);

    expect(
      containsAny(source, [
        /test\s*\(\s*["'`][^"'`]*no declared inputs[^"'`]*starts immediately/i,
        /test\s*\(\s*["'`][^"'`]*without opening the inputs modal/i,
      ]),
      "Expected the no-declared-input immediate run browser flow.",
    ).toBe(true);

    expect(
      containsAny(source, [
        /test\s*\(\s*["'`][^"'`]*dirty workflow[^"'`]*backend simulation[^"'`]*schema[^"'`]*snapshot/i,
        /test\s*\(\s*["'`][^"'`]*simulation input schema/i,
      ]),
      "Expected the dirty workflow backend simulation schema/snapshot browser flow.",
    ).toBe(true);

    expect(
      containsAny(source, [
        /test\s*\(\s*["'`][^"'`]*sensitive values stay hidden[^"'`]*history[^"'`]*rerun[^"'`]*copy[^"'`]*errors/i,
        /test\s*\(\s*["'`][^"'`]*backend validation[^"'`]*sensitive values stay hidden/i,
      ]),
      "Expected the sensitive value validation/history/rerun/copy/error browser flow.",
    ).toBe(true);

    expect(
      countBehaviorAssertions(source),
      "Typed workflow input browser spec should retain behavior assertions, not pass governance by deleting flows.",
    ).toBeGreaterThanOrEqual(55);

    const assertionContracts = [
      [/expectInlineFieldError\(dialog,\s*["']Query["'],\s*["']This field is required\./, "required field validation"],
      [/workflow_inputs\?\.query\?\.value\)\.toBe\(firstQuery\)/, "required input run snapshot"],
      [/openFirstRerunModal[\s\S]*toHaveValue\(firstQuery\)/, "rerun prefill"],
      [/getByRole\("dialog"\)\)\.toHaveCount\(0\)/, "no-input modal absence"],
      [/workflow_inputs\s*\?\?\s*null\)\.toEqual\(\{\}\)/, "no-input run snapshot"],
      [/simulation\.branch\)\.not\.toBe\(["']main["']\)/, "dirty simulation branch"],
      [/workflow_input_schema\)\.toEqual\(realSimulation\?\.input_schema\)/, "dirty workflow schema snapshot"],
      [/expectNoVisibleSecret\(page,\s*firstSecret\)/, "sensitive first secret hidden"],
      [/expectNoVisibleSecret\(page,\s*secondSecret\)/, "sensitive second secret hidden"],
      [/JSON\.parse\(firstCopied\)\)\.not\.toHaveProperty\(["']api_token["']\)/, "first copy omits sensitive input"],
      [/JSON\.parse\(rerunCopied\)\)\.not\.toHaveProperty\(["']api_token["']\)/, "rerun copy omits sensitive input"],
      [/workflowRunCount\(workflow\.id\)\)\.toBe\(countBeforeBlankRerun\)/, "blank sensitive rerun does not create a run"],
      [/interceptBackendConfigValidationError/, "backend validation route interception"],
    ] as const;

    for (const [pattern, label] of assertionContracts) {
      expect(source, `Expected the spec to keep ${label}.`).toMatch(pattern);
    }
  });
});
