import { expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

import { getE2ERuntimeRoot, resolveE2ERuntimePath } from "./runtimeRoot";
import { API, applyFixture } from "./shellReady";

const projectRoot = getE2ERuntimeRoot();
const dbPath = resolveE2ERuntimePath(".runsight", "runsight.db");
const canvasSidecarPath = resolveE2ERuntimePath(
  "custom",
  "workflows",
  ".canvas",
  "research-review.canvas.json",
);

export const readonlySurfaceFixture = {
  baselineRunId: "seed_rr_baseline",
  runId: "seed_rr_regression",
  workflowId: "research-review",
  workflowName: "Research & Review",
} as const;

const readonlyCanvasFixture = {
  nodes: [
    { id: "research", position: { x: 40, y: 60 } },
    { id: "write_summary", position: { x: 360, y: 80 } },
    { id: "quality_review", position: { x: 680, y: 100 } },
    { id: "notify", position: { x: 1000, y: 120 } },
  ],
  edges: [
    { id: "research-write_summary", source: "research", target: "write_summary" },
    {
      id: "write_summary-quality_review",
      source: "write_summary",
      target: "quality_review",
    },
    { id: "quality_review-notify", source: "quality_review", target: "notify" },
  ],
  viewport: { x: 0, y: 0, zoom: 1 },
  selected_node_id: null,
  canvas_mode: "dag",
} as const;

const readonlyWorkflowYaml = `version: '1.0'
id: research-review
kind: workflow
tools:
  - fixture_payload_builder
  - fixture_webhook
souls:
  fixture_notifier:
    id: fixture_notifier
    kind: soul
    name: Fixture Reporter
    role: Fixture Reporter
    system_prompt: >
      Post the provided summary to the fixture channel using the tools available to you.
      Use fixture_payload_builder to format the message, then fixture_webhook to send it.
    provider: test
    model_name: test
    tools:
      - fixture_payload_builder
      - fixture_webhook
blocks:
  research:
    type: linear
    soul_ref: researcher
  write_summary:
    type: linear
    soul_ref: writer
  quality_review:
    type: gate
    soul_ref: reviewer
    eval_key: write_summary
  notify:
    type: linear
    soul_ref: fixture_notifier
workflow:
  name: Research & Review
  entry: research
  transitions:
    - from: research
      to: write_summary
    - from: write_summary
      to: quality_review
    - from: quality_review
      to: notify
`;

let originalCanvasSidecar: string | null = null;

type ApiRequest = {
  delete: (url: string) => Promise<{ status: () => number }>;
};

export type RunSummary = {
  id: string;
  workflow_id: string;
  workflow_name: string;
  status: string;
  commit_sha: string;
  total_cost_usd: number | null;
  regression_count?: number | null;
  run_number?: number | null;
};

export type RunListResponse = {
  items: RunSummary[];
};

export async function fetchReadonlyRunList(): Promise<RunListResponse> {
  return apiGet<RunListResponse>("/runs");
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`);
  expect(response.ok, `GET ${path} failed with ${response.status}`).toBeTruthy();
  return (await response.json()) as T;
}

async function apiDelete(request: ApiRequest, path: string) {
  const response = await request.delete(`${API}${path}`);
  expect(
    [200, 404].includes(response.status()),
    `DELETE ${path} failed with ${response.status()}`,
  ).toBeTruthy();
}

async function seedReadonlyWorkflowFixture() {
  const response = await fetch(`${API}/workflows`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: readonlySurfaceFixture.workflowName,
      yaml: readonlyWorkflowYaml,
      canvas_state: readonlyCanvasFixture,
      commit: true,
    }),
  });

  expect(
    response.ok,
    `POST /workflows failed with ${response.status}: ${await response.text()}`,
  ).toBe(true);
}

function seedReadonlyRunFixture() {
  const commitSha = execFileSync("git", ["rev-parse", "HEAD"], {
    cwd: projectRoot,
    encoding: "utf-8",
  }).trim();

  execFileSync("python3", [
    "-c",
    `
import json
import sqlite3
import sys
import time

db_path, commit_sha, baseline_run_id, current_run_id = sys.argv[1:5]
workflow_id = "research-review"
workflow_name = "Research & Review"
now = time.time()

conn = sqlite3.connect(db_path)
cur = conn.cursor()
run_ids = (baseline_run_id, current_run_id)
cur.execute(
    "delete from logentry where run_id in (?, ?)",
    run_ids,
)
cur.execute(
    "delete from runnode where run_id in (?, ?)",
    run_ids,
)
cur.execute(
    "delete from run where id in (?, ?)",
    run_ids,
)

def insert_run(run_id, created_at, total_cost, total_tokens):
    cur.execute(
        """
        insert into run (
            id, workflow_id, workflow_name, status, task_json, started_at,
            completed_at, duration_s, total_cost_usd, total_tokens, branch,
            source, commit_sha, created_at, updated_at, depth
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            workflow_id,
            workflow_name,
            "completed",
            "{}",
            created_at,
            created_at + 4,
            4,
            total_cost,
            total_tokens,
            "main",
            "manual",
            commit_sha,
            created_at,
            created_at + 4,
            0,
        ),
    )

def insert_node(run_id, node_id, block_type, cost, tokens, score, passed, created_at):
    cur.execute(
        """
        insert into runnode (
            id, run_id, node_id, block_type, status, started_at, completed_at,
            duration_s, cost_usd, tokens, output, soul_id, model_name,
            prompt_hash, soul_version, eval_score, eval_passed, eval_results,
            created_at, updated_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"{run_id}:{node_id}",
            run_id,
            node_id,
            block_type,
            "completed",
            created_at,
            created_at + 1,
            1,
            cost,
            json.dumps({"input": tokens // 2, "output": tokens // 2, "total": tokens}),
            f"{node_id} output",
            f"{node_id}_soul",
            "fixture-readonly-model",
            f"{node_id}_prompt",
            "v1",
            score,
            1 if passed else 0,
            json.dumps({"assertions": []}),
            created_at,
            created_at + 1,
        ),
    )

baseline_created = now - 120
current_created = now - 60
insert_run(baseline_run_id, baseline_created, 0.04, 4000)
insert_run(current_run_id, current_created, 0.12, 9000)

baseline_nodes = [
    ("research", "linear", 0.01, 1000, 0.95, True),
    ("write_summary", "linear", 0.01, 1000, 0.94, True),
    ("quality_review", "gate", 0.01, 1000, 0.93, True),
    ("notify", "linear", 0.01, 1000, 0.92, True),
]
current_nodes = [
    ("research", "linear", 0.03, 3000, 0.70, False),
    ("write_summary", "linear", 0.03, 3000, 0.70, False),
    ("quality_review", "gate", 0.01, 1500, 0.70, False),
    ("notify", "linear", 0.01, 1500, 0.92, True),
]

for index, node in enumerate(baseline_nodes):
    insert_node(baseline_run_id, *node, baseline_created + index)
for index, node in enumerate(current_nodes):
    insert_node(current_run_id, *node, current_created + index)

conn.commit()
conn.close()
`,
    dbPath,
    commitSha,
    readonlySurfaceFixture.baselineRunId,
    readonlySurfaceFixture.runId,
  ], { cwd: projectRoot });
}

function seedReadonlyCanvasFixture() {
  originalCanvasSidecar = existsSync(canvasSidecarPath)
    ? readFileSync(canvasSidecarPath, "utf-8")
    : null;

  mkdirSync(dirname(canvasSidecarPath), { recursive: true });
  writeFileSync(canvasSidecarPath, `${JSON.stringify(readonlyCanvasFixture, null, 2)}\n`);
}

function cleanupReadonlyCanvasFixture() {
  if (originalCanvasSidecar != null) {
    mkdirSync(dirname(canvasSidecarPath), { recursive: true });
    writeFileSync(canvasSidecarPath, originalCanvasSidecar);
    return;
  }

  rmSync(canvasSidecarPath, { force: true });
}

function cleanupReadonlyRunFixture() {
  execFileSync("python3", [
    "-c",
    `
import sqlite3
import sys

db_path, baseline_run_id, current_run_id = sys.argv[1:4]
run_ids = (baseline_run_id, current_run_id)
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("delete from logentry where run_id in (?, ?)", run_ids)
cur.execute("delete from runnode where run_id in (?, ?)", run_ids)
cur.execute("delete from run where id in (?, ?)", run_ids)
conn.commit()
conn.close()
`,
    dbPath,
    readonlySurfaceFixture.baselineRunId,
    readonlySurfaceFixture.runId,
  ], { cwd: projectRoot });
}

export async function setupReadonlySurfaceFixture() {
  await applyFixture([
    {
      id: "readonly-fixture-provider",
      name: "Readonly Fixture",
      type: "readonly-fixture-provider",
      status: "connected",
      is_active: true,
      models: ["readonly-fixture-model"],
      api_key: null,
    },
  ], {
    onboarding_completed: true,
    fallback_enabled: false,
  });
  await seedReadonlyWorkflowFixture();
  seedReadonlyRunFixture();
  seedReadonlyCanvasFixture();
}

export async function cleanupReadonlySurfaceFixture(
  request: ApiRequest,
  forkedWorkflowIds: Iterable<string>,
) {
  cleanupReadonlyRunFixture();
  cleanupReadonlyCanvasFixture();
  for (const workflowId of forkedWorkflowIds) {
    await apiDelete(request, `/workflows/${workflowId}`);
  }
  await apiDelete(request, `/workflows/${readonlySurfaceFixture.workflowId}`);
}
