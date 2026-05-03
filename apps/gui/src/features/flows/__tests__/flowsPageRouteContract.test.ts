import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const flowsSource = readFileSync(resolve(__dirname, "..", "FlowsPage.tsx"), "utf-8");

describe("/flows route contract", () => {
  it("renders the Flows page with the workflows tab as the only tab surface", () => {
    expect(flowsSource).toMatch(/title="Flows"/);
    expect(flowsSource).toMatch(/value="workflows"/);
    expect(flowsSource).toMatch(/Workflows/);
    expect(flowsSource).not.toMatch(/value="runs"/);
    expect(flowsSource).not.toMatch(/useSearchParams/);
  });

  it("keeps the New Workflow action and loading placeholders under the page header", () => {
    expect(flowsSource).toMatch(/New Workflow/);
    expect(flowsSource).toMatch(/PageHeader/);
    expect(flowsSource).toMatch(/WorkflowsTab/);
  });

  it("creates an empty workflow and navigates to its editor from the header action", () => {
    expect(flowsSource).toMatch(/useCreateWorkflow/);
    expect(flowsSource).toMatch(/navigate\(`\/workflows\/\$\{/);
    expect(flowsSource).toMatch(/\/edit`\)/);
  });
});
