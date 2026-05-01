import { stringify } from "yaml";
import type { WorkflowCreate } from "@runsight/shared/zod";

const WORKFLOW_ID_PATTERN = /^[a-z](?:[a-z0-9_-]{1,98})[a-z0-9]$/;

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]+/g, "")
    .replace(/-{2,}/g, "-")
    .replace(/^-|-$/g, "");
}

export const DEFAULT_WORKFLOW_NAME = "Untitled Workflow";

export function deriveWorkflowId(name: string): string {
  return slugify(name).slice(0, 100);
}

export function isValidWorkflowId(id: string): boolean {
  return WORKFLOW_ID_PATTERN.test(id);
}

export function buildBlankWorkflowYaml(workflowId: string, workflowName: string): string {
  return stringify({
    version: "1.0",
    id: workflowId,
    kind: "workflow",
    enabled: false,
    blocks: {},
    workflow: {
      name: workflowName,
      entry: "start",
      transitions: [],
    },
  });
}

export function buildBlankWorkflowCreate(): WorkflowCreate {
  const baseId = deriveWorkflowId(DEFAULT_WORKFLOW_NAME);
  const uniqueSuffix = `${Date.now().toString(36)}-${Math.random()
    .toString(36)
    .slice(2, 8)}`;
  const workflowId = `${baseId}-${uniqueSuffix}`;

  return {
    name: DEFAULT_WORKFLOW_NAME,
    yaml: buildBlankWorkflowYaml(workflowId, DEFAULT_WORKFLOW_NAME),
    canvas_state: {
      nodes: [],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
      selected_node_id: null,
      canvas_mode: "dag",
    },
    commit: false,
  };
}
