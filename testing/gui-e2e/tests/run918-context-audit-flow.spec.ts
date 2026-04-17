import { expect, test, type Page, type Route } from "@playwright/test";

test.describe.configure({ mode: "serial" });

test.beforeEach(({ page }) => {
  page.on("pageerror", (error) => {
    console.log(`pageerror: ${error.message}`);
  });
  page.on("console", (message) => {
    if (message.type() === "error") {
      console.log(`browser console error: ${message.text()}`);
    }
  });
});

const WORKFLOW_ID = "wf_context_governance_918";
const COMPLETED_RUN_ID = "run_918_completed";
const LIVE_RUN_ID = "run_918_live";

const LONG_REF =
  "metadata.secrets.customer_accounts.production.credentials.primary.api_key.value";
const LONG_PREVIEW =
  "This preview is intentionally long enough to exercise wrapping in the audit table on narrow and wide viewports without depending on color-only severity cues.";

type AuditEvent = {
  schema_version: "context_audit.v1";
  event: "context_resolution";
  run_id: string;
  workflow_name: string;
  node_id: string;
  block_type: string;
  access: "declared";
  mode: "strict" | "dev";
  sequence: number;
  records: Array<{
    input_name: string | null;
    from_ref: string | null;
    namespace: "results" | "shared_memory" | "metadata" | null;
    source: string | null;
    field_path?: string | null;
    status: "resolved" | "missing" | "denied" | "empty";
    severity: "allow" | "warn" | "error";
    value_type?: string | null;
    preview?: string | null;
    reason?: string | null;
    internal?: boolean;
  }>;
  resolved_count: number;
  denied_count: number;
  warning_count: number;
  emitted_at: string;
};

function workflowYaml() {
  return `version: "1.0"
id: ${WORKFLOW_ID}
kind: workflow
blocks:
  secret_producer:
    type: code
    code: |
      def main(data):
          return {"public_summary": "safe", "secret": "hidden"}
  declared_consumer:
    type: linear
    soul_ref: analyst
    inputs:
      summary:
        from: secret_producer.public_summary
  strict_missing:
    type: linear
    soul_ref: analyst
    inputs:
      api_key:
        from: ${LONG_REF}
  declared_code:
    type: code
    inputs:
      summary:
        from: secret_producer.public_summary
    code: |
      def main(data):
          return {"keys": list(data.keys()), "summary": data["summary"]}
workflow:
  name: Context Governance 918
  entry: secret_producer
  transitions:
    - from: secret_producer
      to: declared_consumer
    - from: declared_consumer
      to: strict_missing
    - from: strict_missing
      to: declared_code
    - from: declared_code
      to: null
`;
}

function canvasState() {
  return {
    nodes: [
      node("secret_producer", "Secret Producer", 40, 80),
      node("declared_consumer", "Declared Consumer", 360, 80),
      node("strict_missing", "Strict Missing", 680, 80),
      node("declared_code", "Declared Inspector", 1000, 80),
    ],
    edges: [
      edge("secret_producer-declared_consumer", "secret_producer", "declared_consumer"),
      edge("declared_consumer-strict_missing", "declared_consumer", "strict_missing"),
      edge("strict_missing-declared_code", "strict_missing", "declared_code"),
    ],
    viewport: { x: 0, y: 0, zoom: 1 },
    selected_node_id: null,
    canvas_mode: "dag",
  };
}

function node(id: string, name: string, x: number, y: number) {
  return {
    id,
    type: "start",
    position: { x, y },
    data: {
      stepId: id,
      name,
      stepType: id === "declared_code" ? "code" : "linear",
      soulRef: id === "declared_code" ? undefined : "analyst",
      status: "idle",
    },
  };
}

function edge(id: string, source: string, target: string) {
  return {
    id,
    source,
    target,
    type: "straight",
  };
}

function run(id: string, status: "completed" | "running" | "failed") {
  return {
    id,
    workflow_id: WORKFLOW_ID,
    workflow_name: "Context Governance 918",
    status,
    error: status === "failed" ? "Strict missing ref failed the run" : null,
    started_at: 1776370000,
    completed_at: status === "completed" ? 1776370017 : null,
    duration_seconds: status === "completed" ? 17 : null,
    total_cost_usd: 0.042,
    total_tokens: 1234,
    created_at: 1776370000,
    branch: "main",
    source: "manual",
    commit_sha: "abc918",
    run_number: status === "completed" ? 918 : 919,
    regression_count: 0,
  };
}

function runNodes(runId: string) {
  return [
    runNode(runId, "secret_producer", "completed", null),
    runNode(runId, "declared_consumer", "completed", null),
    runNode(
      runId,
      "strict_missing",
      runId === LIVE_RUN_ID ? "running" : "failed",
      "Context resolution failed for missing api_key",
    ),
    runNode(runId, "declared_code", runId === LIVE_RUN_ID ? "pending" : "completed", null),
  ];
}

function runNode(
  runId: string,
  nodeId: string,
  status: "completed" | "running" | "failed" | "pending",
  error: string | null,
) {
  return {
    id: `${runId}:${nodeId}`,
    run_id: runId,
    node_id: nodeId,
    block_type: nodeId === "declared_code" ? "code" : "linear",
    status,
    started_at: 1776370001,
    completed_at: status === "completed" || status === "failed" ? 1776370002 : null,
    duration_seconds: status === "completed" || status === "failed" ? 1 : null,
    cost_usd: 0.01,
    tokens: { input: 10, output: 20, total: 30 },
    error,
    output: status === "completed" ? `${nodeId} output` : null,
    soul_id: nodeId === "declared_code" ? null : "analyst",
    model_name: nodeId === "declared_code" ? null : "gpt-4o",
  };
}

function workflow() {
  return {
    kind: "workflow",
    id: WORKFLOW_ID,
    name: "Context Governance 918",
    description: "Fixture workflow for context governance E2E.",
    yaml: workflowYaml(),
    canvas_state: canvasState(),
    valid: true,
    block_count: 4,
    enabled: true,
    commit_sha: "abc918",
  };
}

function auditEvent(overrides: Partial<AuditEvent>): AuditEvent {
  return {
    schema_version: "context_audit.v1",
    event: "context_resolution",
    run_id: COMPLETED_RUN_ID,
    workflow_name: "Context Governance 918",
    node_id: "declared_consumer",
    block_type: "linear",
    access: "declared",
    mode: "strict",
    sequence: 1,
    records: [
      {
        input_name: "summary",
        from_ref: "secret_producer.public_summary",
        namespace: "results",
        source: "secret_producer",
        field_path: "public_summary",
        status: "resolved",
        severity: "allow",
        value_type: "str",
        preview: "safe",
        reason: null,
        internal: false,
      },
    ],
    resolved_count: 1,
    denied_count: 0,
    warning_count: 0,
    emitted_at: "2026-04-17T00:00:01.000Z",
    ...overrides,
  };
}

function historicalAuditEvents(runId = COMPLETED_RUN_ID): AuditEvent[] {
  return [
    auditEvent({ run_id: runId, node_id: "declared_consumer", sequence: 1 }),
    auditEvent({
      run_id: runId,
      node_id: "strict_missing",
      sequence: 2,
      records: [
        {
          input_name: "api_key",
          from_ref: LONG_REF,
          namespace: "metadata",
          source: "secrets",
          field_path: "customer_accounts.production.credentials.primary.api_key.value",
          status: "missing",
          severity: "error",
          value_type: null,
          preview: LONG_PREVIEW,
          reason: "strict declared ref missing",
          internal: false,
        },
      ],
      resolved_count: 0,
      denied_count: 1,
      warning_count: 0,
      emitted_at: "2026-04-17T00:00:02.000Z",
    }),
    auditEvent({
      run_id: runId,
      node_id: "declared_code",
      block_type: "code",
      sequence: 3,
      resolved_count: 1,
      denied_count: 0,
      warning_count: 0,
      emitted_at: "2026-04-17T00:00:03.000Z",
    }),
  ];
}

async function installRoutes(
  page: Page,
  options?: { liveAudit?: boolean },
): Promise<{ contextAuditRequests: string[]; workflowCreateBodies: unknown[] }> {
  const contextAuditRequests: string[] = [];
  const workflowCreateBodies: unknown[] = [];

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!url.pathname.startsWith("/api/")) {
      return route.fallback();
    }
    const path = `${url.pathname}${url.search}`;

    if (path === "/api/settings/app") {
      return json(route, { onboarding_completed: true, fallback_enabled: false });
    }
    if (path === `/api/runs/${COMPLETED_RUN_ID}`) {
      return json(route, run(COMPLETED_RUN_ID, "completed"));
    }
    if (path === `/api/runs/${LIVE_RUN_ID}`) {
      return json(route, run(LIVE_RUN_ID, "running"));
    }
    if (path === `/api/runs/${COMPLETED_RUN_ID}/nodes`) {
      return json(route, runNodes(COMPLETED_RUN_ID));
    }
    if (path === `/api/runs/${LIVE_RUN_ID}/nodes`) {
      return json(route, runNodes(LIVE_RUN_ID));
    }
    if (path.startsWith(`/api/workflows/${WORKFLOW_ID}`)) {
      return json(route, workflow());
    }
    if (path.startsWith("/api/runs?")) {
      const currentRun = path.includes(LIVE_RUN_ID)
        ? run(LIVE_RUN_ID, "running")
        : run(COMPLETED_RUN_ID, "completed");
      return json(route, { items: [currentRun], total: 1, offset: 0, limit: 50 });
    }
    if (path.endsWith("/logs")) {
      return json(route, { items: [], total: 0, offset: 0, limit: 100 });
    }
    if (path.endsWith("/regressions")) {
      return json(route, { count: 0, issues: [] });
    }
    if (path.includes("/context-audit")) {
      contextAuditRequests.push(path);
      const runId = path.includes(LIVE_RUN_ID) ? LIVE_RUN_ID : COMPLETED_RUN_ID;
      return json(route, {
        items: options?.liveAudit ? [] : historicalAuditEvents(runId),
        page_size: 100,
        has_next_page: false,
        end_cursor: null,
      });
    }
    if (path === `/api/runs/${LIVE_RUN_ID}/stream`) {
      return sse(route, [
        { event: "context_resolution", data: "{not-json" },
        {
          event: "context_resolution",
          data: JSON.stringify(
            auditEvent({
              run_id: LIVE_RUN_ID,
              node_id: "strict_missing",
              sequence: 10,
              records: [
                {
                  input_name: "api_key",
                  from_ref: LONG_REF,
                  namespace: "metadata",
                  source: "secrets",
                  field_path: "customer_accounts.production.credentials.primary.api_key.value",
                  status: "denied",
                  severity: "error",
                  value_type: null,
                  preview: LONG_PREVIEW,
                  reason: "strict declared ref denied",
                  internal: false,
                },
              ],
              resolved_count: 0,
              denied_count: 1,
              warning_count: 0,
              emitted_at: "2026-04-17T00:01:10.000Z",
            }),
          ),
        },
        {
          event: "node_failed",
          data: JSON.stringify({ node_id: "strict_missing", error: "strict declared ref denied" }),
        },
        {
          event: "run_failed",
          data: JSON.stringify({ run_id: LIVE_RUN_ID, error: "strict declared ref denied" }),
        },
      ]);
    }
    if (path.endsWith("/stream")) {
      return sse(route, []);
    }
    if (path.startsWith("/api/git/file")) {
      return json(route, {
        path: `custom/workflows/${WORKFLOW_ID}.yaml`,
        ref: "abc918",
        content: workflowYaml(),
      });
    }
    if (request.method() === "POST" && path === "/api/workflows") {
      const body = request.postDataJSON();
      workflowCreateBodies.push(body);
      return json(route, {
        ...workflow(),
        id: "drft-context-governance-918-a1b2",
        name: "Context Governance 918 fork",
        yaml: String(body.yaml ?? ""),
      });
    }
    if (path === "/api/workflows/drft-context-governance-918-a1b2") {
      return json(route, {
        ...workflow(),
        id: "drft-context-governance-918-a1b2",
        name: "Context Governance 918 fork",
      });
    }

    return json(route, { error: `Unhandled E2E fixture route: ${path}` }, 404);
  });

  return { contextAuditRequests, workflowCreateBodies };
}

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function sse(route: Route, events: Array<{ event: string; data: string }>) {
  await route.fulfill({
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
    body: events.map(({ event, data }) => `event: ${event}\ndata: ${data}\n\n`).join(""),
  });
}

async function openAuditTab(page: Page) {
  await expect(page.getByTestId("surface-topbar")).toBeVisible({ timeout: 15000 });
  await expect(page.getByTestId("surface-center")).toBeVisible({ timeout: 15000 });
  await page.getByTestId("workflow-audit-tab").click();
  await expect(page.getByTestId("workflow-audit-panel")).toBeVisible({ timeout: 15000 });
}

test("completed run loads historical audit records, access badges, long rows, and clean fork payload", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1366, height: 900 });
  const { contextAuditRequests, workflowCreateBodies } = await installRoutes(page);

  await page.goto(`/runs/${COMPLETED_RUN_ID}`);
  await openAuditTab(page);

  await expect
    .poll(() => contextAuditRequests.some((path) => path.includes("page_size=100")))
    .toBe(true);

  const auditPanel = page.getByTestId("workflow-audit-panel");
  await expect(auditPanel).toContainText("declared_consumer");
  await expect(auditPanel).toContainText("secret_producer.public_summary");
  await expect(auditPanel).toContainText("strict_missing");
  await expect(auditPanel).toContainText("missing");
  await expect(auditPanel).toContainText("error");
  await expect(auditPanel).toContainText(LONG_REF);
  await expect(auditPanel).toContainText("declared_code");
  await expect(auditPanel).not.toContainText("all_access");

  await expect(page.getByTestId("node-Declared Inspector")).toContainText("Access declared");
  await expect(page.getByTestId("node-Strict Missing")).toContainText("Denied 1");
  await expect(page.locator(".react-flow__edge.context-overlay")).toHaveCount(1);

  await expectNoDocumentHorizontalOverflow(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(auditPanel).toContainText(LONG_REF);
  await expect(auditPanel).toContainText("missing");
  await expect(auditPanel).toContainText("error");
  await expectNoDocumentHorizontalOverflow(page);

  await page.setViewportSize({ width: 1366, height: 900 });
  await page.getByRole("button", { name: "Fork" }).click();
  await expect
    .poll(() => workflowCreateBodies.length, { timeout: 15000 })
    .toBe(1);
  expect(JSON.stringify(workflowCreateBodies[0])).not.toContain("context-overlay");
  expect(JSON.stringify(workflowCreateBodies[0])).not.toContain("contextOverlay");
  expect(JSON.stringify(workflowCreateBodies[0])).not.toContain("access: all");
});

test("active run appends live context_resolution SSE and ignores malformed audit events", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 820 });
  const { contextAuditRequests } = await installRoutes(page, { liveAudit: true });

  await page.goto(`/runs/${LIVE_RUN_ID}`);
  await openAuditTab(page);

  await expect
    .poll(() => contextAuditRequests.some((path) => path.includes(LIVE_RUN_ID)))
    .toBe(true);

  const auditPanel = page.getByTestId("workflow-audit-panel");
  await expect(auditPanel).toContainText("strict_missing", { timeout: 15000 });
  await expect(auditPanel).toContainText("denied");
  await expect(auditPanel).toContainText("error");
  await expect(auditPanel).toContainText(LONG_REF);

  const strictMissingNode = page.getByTestId("node-Strict Missing");
  await expect(strictMissingNode).toContainText("Failed");
  await expect(strictMissingNode).toContainText("Denied 1");

  await auditPanel.getByRole("button", { name: "Open context audit for strict_missing" }).click();
  const inspector = page.getByTestId("right-inspector");
  await expect(inspector).toBeVisible({ timeout: 15000 });
  await expect(inspector.getByRole("tab", { name: "Context" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(inspector).toContainText("Access declared");
  await expect(inspector).toContainText("denied");
  await expect(inspector).toContainText("error");
});

async function expectNoDocumentHorizontalOverflow(page: Page) {
  await expect
    .poll(async () =>
      page.evaluate(() => {
        const root = document.documentElement;
        return root.scrollWidth - root.clientWidth;
      }),
    )
    .toBeLessThanOrEqual(1);
}
