/**
 * Governance coverage for context audit E2E ownership.
 *
 * Owner: testing/gui-e2e owns browser-flow behavior assertions.
 * Boundary: context audit route fixtures, YAML/canvas/run builders, JSON/SSE
 * response helpers, and route installation belong in behavior-named helpers or
 * fixtures, not in the Playwright spec.
 * Exit criteria: delete this suite once lint rules or stable E2E fixture
 * conventions enforce the same context audit ownership boundary.
 */

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const TESTS_DIR = resolve(__dirname, "..");
const HELPERS_DIR = resolve(TESTS_DIR, "helpers");
const FIXTURES_DIR = resolve(TESTS_DIR, "fixtures");
const CONTEXT_AUDIT_SPEC = resolve(TESTS_DIR, "context-audit-flow.spec.ts");

const INLINE_FIXTURE_HELPERS = [
  "workflowYaml",
  "canvasState",
  "node",
  "edge",
  "run",
  "runNodes",
  "runNode",
  "workflow",
  "auditEvent",
  "historicalAuditEvents",
  "installRoutes",
  "json",
  "sse",
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

function readContextAuditSpec(): string {
  return readFile(CONTEXT_AUDIT_SPEC);
}

function readContextAuditFixtureFiles(): SourceFile[] {
  return [HELPERS_DIR, FIXTURES_DIR]
    .filter((dir) => existsSync(dir))
    .flatMap((dir) =>
      readdirSync(dir)
        .filter((fileName) => /context[-_\w]*audit|audit[-_\w]*context/i.test(fileName))
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

describe("Context audit E2E ownership governance", () => {
  it("keeps context audit route fixtures and key ids in behavior-named helper files", () => {
    const fixtureFiles = readContextAuditFixtureFiles();

    expect(
      fixtureFiles.map((file) => file.name),
      "Expected context audit fixtures under tests/helpers or tests/fixtures, for example context-audit-fixture.ts.",
    ).not.toEqual([]);

    const helperSources = fixtureFiles.map((file) => file.source).join("\n");
    const exportsRouteInstaller =
      /export\s+(?:async\s+)?function\s+install\w*Context\w*Audit\w*Routes\b/i.test(
        stripComments(helperSources),
      ) ||
      /export\s+const\s+install\w*Context\w*Audit\w*Routes\b/i.test(
        stripComments(helperSources),
      ) ||
      exportsNamedValue(helperSources, "installRoutes");

    expect(
      exportsRouteInstaller,
      "Context audit helper should export route installation so the spec only installs fixtures and asserts behavior.",
    ).toBe(true);

    for (const exportedId of ["WORKFLOW_ID", "COMPLETED_RUN_ID", "LIVE_RUN_ID", "LONG_REF"]) {
      expect(
        exportsNamedValue(helperSources, exportedId),
        `${exportedId} should be exported by the context audit helper/fixture instead of owned by the spec.`,
      ).toBe(true);
    }
  });

  it("keeps the context audit browser spec free of inline fixture, builder, and route helper definitions", () => {
    const source = readContextAuditSpec();
    const inlineDefinitions = INLINE_FIXTURE_HELPERS.filter((helperName) =>
      definesHelperInline(source, helperName),
    );

    expect(
      inlineDefinitions,
      "context-audit-flow.spec.ts should import fixture builders and route installation from a context audit helper/fixture.",
    ).toEqual([]);
  });

  it("keeps the spec attached to the context audit fixture owner without banning harmless helper calls", () => {
    const source = stripComments(readContextAuditSpec());

    expect(
      source,
      "The browser spec should import context audit route fixtures from tests/helpers or tests/fixtures.",
    ).toMatch(/from\s+["']\.\/(?:helpers|fixtures)\/[^"']*context[-_\w]*audit[^"']*["']/i);
  });

  it("preserves the two behavior-owned browser flows and their observable assertions", () => {
    const source = readContextAuditSpec();

    expect(
      containsAny(source, [
        /test\s*\(\s*["'`][^"'`]*(?:completed|historical)[^"'`]*audit/i,
        /test\s*\(\s*["'`][^"'`]*audit[^"'`]*(?:completed|historical)/i,
      ]),
      "Expected a completed/historical context audit browser flow.",
    ).toBe(true);

    expect(
      containsAny(source, [
        /test\s*\(\s*["'`][^"'`]*(?:live|active|SSE)[^"'`]*audit/i,
        /test\s*\(\s*["'`][^"'`]*audit[^"'`]*(?:live|active|SSE)/i,
      ]),
      "Expected a live SSE context audit browser flow.",
    ).toBe(true);

    expect(
      countBehaviorAssertions(source),
      "Context audit browser spec should retain behavior assertions, not pass governance by deleting the flows.",
    ).toBeGreaterThanOrEqual(20);

    const assertionContracts = [
      [/workflow-audit-panel/, "audit panel"],
      [/contextAuditRequests/, "context audit request tracking"],
      [/expectNoDocumentHorizontalOverflow/, "responsive overflow assertion"],
      [/workflowCreateBodies[\s\S]*not\.toContain[\s\S]*context-overlay/, "fork payload sanitization"],
      [/\bdenied\b[\s\S]*\bFailed\b|\bFailed\b[\s\S]*\bdenied\b/i, "live SSE denial and status assertions"],
      [/right-inspector[\s\S]*tab[\s\S]*Context/i, "Context inspector tab assertion"],
    ] as const;

    for (const [pattern, label] of assertionContracts) {
      expect(source, `Expected the spec to keep ${label}.`).toMatch(pattern);
    }
  });
});
