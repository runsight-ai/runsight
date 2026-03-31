import { jsx, jsxs } from "react/jsx-runtime";
import { useNavigate } from "react-router";

interface WorkflowRowProps {
  workflow: {
    id: string;
    name?: string | null;
    block_count?: number | null;
    modified_at?: number | null;
    commit_sha?: string | null;
    health?: {
      run_count?: number | null;
      eval_pass_pct?: number | null;
      total_cost_usd?: number | null;
      regression_count?: number | null;
    } | null;
  };
  onDelete: (workflow: WorkflowRowProps["workflow"]) => void;
}

function formatPlural(value: number, singular: string, plural = `${singular}s`) {
  return `${value} ${value === 1 ? singular : plural}`;
}

function formatCommit(commitSha: string | null | undefined) {
  return commitSha ? commitSha.slice(0, 7) : "uncommitted";
}

function formatRelativeTime(timestamp: number | null | undefined) {
  if (!timestamp) {
    return "Unknown update";
  }

  const secondsAgo = Math.max(0, Math.floor(Date.now() / 1000 - timestamp));

  if (secondsAgo < 60) {
    return "Just now";
  }

  const minutesAgo = Math.floor(secondsAgo / 60);
  if (minutesAgo < 60) {
    return `${minutesAgo}m ago`;
  }

  const hoursAgo = Math.floor(minutesAgo / 60);
  if (hoursAgo < 24) {
    return `${hoursAgo}h ago`;
  }

  const daysAgo = Math.floor(hoursAgo / 24);
  return `${daysAgo}d ago`;
}

function getEvalLabel(workflow: WorkflowRowProps["workflow"]) {
  const evalPassPct = workflow.health?.eval_pass_pct;

  if (evalPassPct == null) {
    return "No runs yet";
  }

  return `${Math.round(evalPassPct)}% eval`;
}

function getCostLabel(workflow: WorkflowRowProps["workflow"]) {
  const runCount = workflow.health?.run_count ?? 0;

  if (runCount === 0) {
    return "— cost";
  }

  return `$${(workflow.health?.total_cost_usd ?? 0).toFixed(2)} cost`;
}

function getRegressionLabel(workflow: WorkflowRowProps["workflow"]) {
  const runCount = workflow.health?.run_count ?? 0;

  if (runCount === 0) {
    return "— regressions";
  }

  return formatPlural(workflow.health?.regression_count ?? 0, "regression");
}

export function Component({ workflow, onDelete }: WorkflowRowProps) {
  const navigate = useNavigate();
  const name = workflow.name?.trim() || "Untitled";
  const runCount = workflow.health?.run_count ?? 0;

  const openWorkflow = () => {
    navigate(`/workflows/${workflow.id}/edit`);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLLIElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openWorkflow();
    }
  };

  const handleDeleteClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    onDelete(workflow);
  };

  return jsxs("li", {
    className:
      "group flex items-start gap-3 rounded-md border border-border-subtle bg-surface-secondary px-4 py-3 transition-colors hover:bg-surface-hover focus-within:bg-surface-hover",
    tabIndex: 0,
    role: "listitem",
    "aria-label": `Open ${name} workflow`,
    onClick: openWorkflow,
    onKeyDown: handleKeyDown,
    children: [
      jsxs("div", {
        className: "min-w-0 flex-1",
        children: [
          jsxs("div", {
            className: "flex flex-wrap items-center gap-x-2 gap-y-1 text-sm",
            children: [
              jsx("span", {
                className: "font-medium text-primary",
                children: name,
              }),
              jsx("span", {
                className: "text-muted",
                children: formatPlural(workflow.block_count ?? 0, "block"),
              }),
              jsx("span", {
                className: "font-mono text-muted",
                children: formatCommit(workflow.commit_sha),
              }),
              jsx("span", {
                className: "text-muted",
                children: formatRelativeTime(workflow.modified_at),
              }),
            ],
          }),
          jsxs("div", {
            className: "mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-secondary",
            children: [
              jsx("span", {
                children: formatPlural(runCount, "run"),
              }),
              jsx("span", {
                children: getEvalLabel(workflow),
              }),
              jsx("span", {
                className: "font-mono",
                children: getCostLabel(workflow),
              }),
              jsx("span", {
                children: getRegressionLabel(workflow),
              }),
            ],
          }),
        ],
      }),
      jsx("button", {
        type: "button",
        "aria-label": `Delete ${name} workflow`,
        className:
          "shrink-0 rounded-md p-2 text-muted opacity-0 pointer-events-none transition-all hover:bg-surface-hover hover:text-primary group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100 focus-visible:pointer-events-auto focus-visible:opacity-100",
        onClick: handleDeleteClick,
        children: jsx("span", {
          "aria-hidden": true,
          children: "🗑",
        }),
      }),
    ],
  });
}

export { Component as WorkflowRow };
