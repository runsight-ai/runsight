import path from "node:path";
import { fileURLToPath } from "node:url";

const helpersDir = path.dirname(fileURLToPath(import.meta.url));
const e2eWorkspaceRoot = path.resolve(helpersDir, "..", "..");
const repoRoot = path.resolve(e2eWorkspaceRoot, "..", "..");

function formatMissingEnv() {
  return [
    "Playwright E2E tests require an isolated runtime root.",
    "Set RUNSIGHT_E2E_PROJECT_ROOT and RUNSIGHT_BASE_PATH via testing/gui-e2e/playwright.config.ts.",
    "Refusing to infer the root from cwd or the running API process.",
  ].join(" ");
}

function assertSafeRuntimeRoot(runtimeRoot: string) {
  if (runtimeRoot === repoRoot) {
    throw new Error(
      `RUNSIGHT_E2E_PROJECT_ROOT resolves to the repository root (${repoRoot}). ` +
        "Refusing to use real repo runtime state for E2E tests.",
    );
  }

  if (runtimeRoot === e2eWorkspaceRoot) {
    throw new Error(
      `RUNSIGHT_E2E_PROJECT_ROOT resolves to the E2E workspace root (${e2eWorkspaceRoot}). ` +
        "Use an isolated child runtime directory instead.",
    );
  }
}

export function getE2ERuntimeRoot() {
  const projectRoot = process.env.RUNSIGHT_E2E_PROJECT_ROOT;
  const basePath = process.env.RUNSIGHT_BASE_PATH;

  if (!projectRoot || !basePath) {
    throw new Error(formatMissingEnv());
  }

  const resolvedProjectRoot = path.resolve(projectRoot);
  const resolvedBasePath = path.resolve(basePath);

  if (resolvedProjectRoot !== resolvedBasePath) {
    throw new Error(
      "RUNSIGHT_E2E_PROJECT_ROOT and RUNSIGHT_BASE_PATH must point at the same " +
        `isolated runtime root. Got ${resolvedProjectRoot} and ${resolvedBasePath}.`,
    );
  }

  assertSafeRuntimeRoot(resolvedProjectRoot);
  return resolvedProjectRoot;
}

export function resolveE2ERuntimePath(...segments: string[]) {
  const runtimeRoot = getE2ERuntimeRoot();
  const resolved = path.resolve(runtimeRoot, ...segments);
  const prefix = `${runtimeRoot}${path.sep}`;

  if (resolved !== runtimeRoot && !resolved.startsWith(prefix)) {
    throw new Error(`Resolved path escapes E2E runtime root: ${resolved}`);
  }

  return resolved;
}
