import { Button } from "@runsight/ui/button";
import { Trash2 } from "lucide-react";
import type { KeyboardEvent, MouseEvent, SyntheticEvent } from "react";
import { useState } from "react";
import { useNavigate } from "react-router";

interface WorkflowRowProps {
  workflow: {
    id: string;
    name?: string | null;
    enabled?: boolean | null;
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
  onToggleEnabled?: (enabled: boolean) => Promise<unknown>;
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

function getSwitchTrackClass(isEnabled: boolean) {
  return [
    "relative h-5 w-9 flex-shrink-0 rounded-full border border-border-default transition-[background,border-color] duration-150 ease-default",
    "focus-visible:outline focus-visible:outline-[var(--focus-ring-width)] focus-visible:outline-[var(--focus-ring-color)] focus-visible:outline-offset-[var(--focus-ring-offset)]",
    isEnabled
      ? "bg-interactive-default border-interactive-default"
      : "bg-neutral-5",
  ].join(" ");
}

function getSwitchThumbClass(isEnabled: boolean) {
  return [
    "absolute left-0.5 top-0.5 h-3.5 w-3.5 rounded-full bg-neutral-12 transition-transform duration-150 ease-[var(--ease-spring)]",
    isEnabled ? "translate-x-4 bg-text-on-accent" : "",
  ].join(" ");
}

function WorkflowEnabledToggle({
  initialEnabled,
  name,
  onToggleEnabled,
}: {
  initialEnabled: boolean;
  name: string;
  onToggleEnabled: (enabled: boolean) => Promise<unknown>;
}) {
  const [isEnabled, setIsEnabled] = useState(initialEnabled);

  const handleToggleEnabled = async (nextEnabled: boolean) => {
    const previousEnabled = isEnabled;
    setIsEnabled(nextEnabled);

    try {
      await onToggleEnabled(nextEnabled);
    } catch (error) {
      console.error("Failed to update workflow enabled state:", error);
      setIsEnabled(previousEnabled);
    }
  };

  return (
    <button
      type="button"
      role="switch"
      aria-checked={isEnabled}
      aria-label={`Enable ${name} workflow`}
      className={getSwitchTrackClass(isEnabled)}
      onClick={() => {
        void handleToggleEnabled(!isEnabled);
      }}
    >
      <span
        aria-hidden="true"
        className={getSwitchThumbClass(isEnabled)}
      />
    </button>
  );
}

function StaticWorkflowEnabledToggle({
  enabled,
  name,
}: {
  enabled: boolean;
  name: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={`Enable ${name} workflow`}
      className={getSwitchTrackClass(enabled)}
    >
      <span
        aria-hidden="true"
        className={getSwitchThumbClass(enabled)}
      />
    </button>
  );
}

export function Component({ workflow, onDelete, onToggleEnabled }: WorkflowRowProps) {
  const navigate = useNavigate();
  const name = workflow.name?.trim() || "Untitled";
  const runCount = workflow.health?.run_count ?? 0;

  const openWorkflow = () => {
    navigate(`/workflows/${workflow.id}/edit`);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLLIElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openWorkflow();
    }
  };

  const handleDeleteClick = (event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    onDelete(workflow);
  };

  const stopRowActivation = (event: SyntheticEvent) => {
    event.stopPropagation();
  };

  return (
    <li
      className="group flex items-start gap-3 rounded-md border border-border-subtle bg-surface-secondary px-4 py-3 transition-colors hover:bg-surface-hover focus-within:bg-surface-hover"
      tabIndex={0}
      role="listitem"
      aria-label={`Open ${name} workflow`}
      onClick={openWorkflow}
      onKeyDown={handleKeyDown}
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
          <span className="font-medium text-primary">{name}</span>
          <span className="text-muted">
            {formatPlural(workflow.block_count ?? 0, "block")}
          </span>
          <span className="font-mono text-muted">{formatCommit(workflow.commit_sha)}</span>
          <span className="text-muted">{formatRelativeTime(workflow.modified_at)}</span>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-secondary">
          <span>{formatPlural(runCount, "run")}</span>
          <span>{getEvalLabel(workflow)}</span>
          <span className="font-mono">{getCostLabel(workflow)}</span>
          <span>{getRegressionLabel(workflow)}</span>
        </div>
      </div>
      <div
        className="flex shrink-0 items-center gap-1"
        onClick={stopRowActivation}
        onKeyDown={stopRowActivation}
      >
        {onToggleEnabled ? (
          <WorkflowEnabledToggle
            initialEnabled={Boolean(workflow.enabled)}
            name={name}
            onToggleEnabled={onToggleEnabled}
          />
        ) : (
          <StaticWorkflowEnabledToggle
            enabled={Boolean(workflow.enabled)}
            name={name}
          />
        )}
        <Button
          type="button"
          variant="icon-only"
          size="sm"
          aria-label={`Delete ${name} workflow`}
          className="rounded-md text-muted opacity-0 transition-all hover:bg-surface-hover hover:text-primary group-hover:opacity-100 group-focus-within:opacity-100 focus-visible:opacity-100"
          onClick={handleDeleteClick}
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
    </li>
  );
}

export { Component as WorkflowRow };
