import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const FEATURE_DIR = resolve(__dirname, "..");

function readFeatureSource(fileName: string): string {
  const filePath = resolve(FEATURE_DIR, fileName);

  expect(
    existsSync(filePath),
    `Expected RUN-426 to add ${fileName} under apps/gui/src/features/flows`,
  ).toBe(true);

  return readFileSync(filePath, "utf-8");
}

describe("RUN-426 flows page shell", () => {
  it("adds the FlowsPage and WorkflowsTab source files for the new /flows screen", () => {
    readFeatureSource("FlowsPage.tsx");
    readFeatureSource("WorkflowsTab.tsx");
  });

  it("renders a Flows page header with a New Workflow action", () => {
    const source = readFeatureSource("FlowsPage.tsx");

    expect(source).toMatch(/PageHeader/);
    expect(source).toMatch(/title="Flows"|title=\{"Flows"\}/);
    expect(source).toMatch(/New Workflow/);
  });

  it("defaults the shell to the Workflows tab and keeps Runs inactive with Coming soon copy", () => {
    const source = readFeatureSource("FlowsPage.tsx");

    expect(source).toMatch(/TabsList/);
    expect(source).toMatch(/TabsTrigger[\s\S]*value=["']workflows["']/);
    expect(source).toMatch(/useState<[^>]+>\("workflows"\)|defaultValue=["']workflows["']/);
    expect(source).toMatch(/TabsTrigger[\s\S]*value=["']runs["']/);
    expect(source).toMatch(/Coming soon/);
    expect(source).toMatch(/value=["']runs["'][\s\S]*?(disabled|aria-disabled=\{true\})/);
  });

  it("keeps the Runs tab as a placeholder instead of wiring the real runs table in RUN-426", () => {
    const source = readFeatureSource("FlowsPage.tsx");

    expect(source).not.toMatch(/RunList/);
    expect(source).toMatch(/Coming soon|Runs tab coming soon|Runs are coming soon/);
  });
});

describe("RUN-426 workflows tab states", () => {
  it("loads workflow data through useWorkflows and renders a search control", () => {
    const source = readFeatureSource("WorkflowsTab.tsx");

    expect(source).toMatch(/useWorkflows/);
    expect(source).toMatch(/Search workflows/);
  });

  it("filters by workflow name only, case-insensitively", () => {
    const source = readFeatureSource("WorkflowsTab.tsx");

    expect(source).toMatch(/name[\s\S]*toLowerCase\(\)[\s\S]*includes\(query\)|workflow\.name/);
    expect(source).not.toMatch(/description[\s\S]*toLowerCase\(\)[\s\S]*includes\(query\)|workflow\.description/);
  });

  it("covers loading, error, empty, and no-search-results states from the spec", () => {
    const source = readFeatureSource("WorkflowsTab.tsx");

    expect(source).toMatch(/isLoading/);
    expect(source).toMatch(/Couldn't load workflows\. Check file permissions on custom\/workflows\//);
    expect(source).toMatch(/Retry/);
    expect(source).toMatch(/No workflows yet/);
    expect(source).toMatch(/Create your first workflow to start orchestrating AI agents/);
    expect(source).toMatch(/No workflows match your search/);
  });

  it("wires retry and delete actions through the workflow query hooks", () => {
    const source = readFeatureSource("WorkflowsTab.tsx");

    expect(source).toMatch(/refetch/);
    expect(source).toMatch(/useDeleteWorkflow/);
    expect(source).toMatch(/DeleteConfirmDialog|Dialog/);
  });

  it("renders the workflow list with semantic container markup", () => {
    const source = readFeatureSource("WorkflowsTab.tsx");

    expect(source).toMatch(/role=["']list["']|<ul\b|<ol\b/);
    expect(source).toMatch(/WorkflowRow/);
  });
});
