/**
 * Governance: token architecture test ownership boundary.
 *
 * This suite intentionally reads the token architecture suite as source text. It
 * guards test shape and ownership metadata, not runtime CSS behavior.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const TOKEN_SUITE_PATH = resolve(__dirname, "tokenArchitecture.test.ts");

function readTokenSuite(): string {
  return readFileSync(TOKEN_SUITE_PATH, "utf-8");
}

function describeBlocks(source: string): string[] {
  return [...source.matchAll(/describe\(\s*["'`]([^"'`]+)["'`]/g)].map(
    (match) => match[1]!
  );
}

describe("token architecture governance boundary", () => {
  it("declares governance metadata for the suite owner, boundary, and exit criteria", () => {
    const source = readTokenSuite();

    expect(source).toMatch(/\bGovernance:/);
    expect(source).toMatch(/\bOwner:/);
    expect(source).toMatch(/\bBoundary:/);
    expect(source).toMatch(/\bExit criteria:/);
  });

  it("keeps the architecture suite compact enough to avoid god-object coverage", () => {
    const source = readTokenSuite();
    const lineCount = source.split(/\r?\n/).length;
    const ownerBlocks = describeBlocks(source);

    expect(lineCount).toBeLessThanOrEqual(550);
    expect(ownerBlocks.length).toBeLessThanOrEqual(18);
  });

  it("rejects unstable framing in headers and describe names", () => {
    const source = readTokenSuite();
    const headerAndDescribeNames = [
      source.slice(0, 800),
      ...describeBlocks(source),
    ].join("\n");

    expect(headerAndDescribeNames).toMatch(/token architecture/i);
    expect(headerAndDescribeNames).toMatch(/Tailwind bridge/i);
    expect(headerAndDescribeNames).toMatch(/retired token absence/i);
    expect(headerAndDescribeNames).toMatch(/global styles\/a11y\/sidebar/i);
    expect(headerAndDescribeNames).not.toMatch(/\bmigration\b/i);
    expect(headerAndDescribeNames).not.toMatch(/\bRUN-\d+\b/i);
  });
});
