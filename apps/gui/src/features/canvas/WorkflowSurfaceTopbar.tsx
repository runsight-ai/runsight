import type { ReactNode } from "react";

import { Button } from "@runsight/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@runsight/ui/tabs";
import { cn } from "@runsight/ui/utils";

import type { WorkflowSurfaceMode } from "./workflowSurfaceContract";

interface WorkflowSurfaceTopbarRun {
  id: string;
  workflow_id?: string | null;
  workflow_name?: string | null;
  status?: string | null;
  total_cost_usd?: number | null;
  total_tokens?: number | null;
  commit_sha?: string | null;
}

interface WorkflowSurfaceTopbarMetrics {
  total_cost_usd?: number | null;
  total_tokens?: number | null;
}

interface WorkflowSurfaceTopbarProps {
  mode: WorkflowSurfaceMode;
  workflowName: string;
  activeTab?: string;
  onTabChange?: (value: string) => void;
  isDirty?: boolean;
  onSave?: () => void;
  onRun?: () => void;
  run?: WorkflowSurfaceTopbarRun;
  metrics?: WorkflowSurfaceTopbarMetrics;
  hasSnapshot?: boolean;
  onFork?: () => void;
  onOpenWorkflow?: () => void;
  leadingContent?: ReactNode;
  runControl?: ReactNode;
}

function formatCost(cost?: number | null) {
  if (cost == null) return "--";
  return `$${cost.toFixed(3)}`;
}

function formatTokens(tokens?: number | null) {
  if (tokens == null) return "--";
  return tokens.toLocaleString();
}

function formatStatus(status?: string | null) {
  if (!status) return null;
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function MetricCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-[var(--border-default)] bg-[var(--surface-raised)] px-3 py-1.5">
      <span className="text-xs text-[var(--text-muted)]">{label}</span>
      <span className="font-mono text-sm text-[var(--text-primary)]">{value}</span>
    </div>
  );
}

export function WorkflowSurfaceTopbar({
  mode,
  workflowName,
  activeTab = "canvas",
  onTabChange,
  isDirty = false,
  onSave,
  onRun,
  run,
  metrics,
  hasSnapshot,
  onFork,
  onOpenWorkflow,
  leadingContent,
  runControl,
}: WorkflowSurfaceTopbarProps) {
  const isWorkflowMode = mode === "workflow" || mode === "fork-draft";
  const isHistoricalMode = mode === "historical";
  const isExecutionMode = mode === "execution";
  const resolvedStatus = run?.status ?? (isExecutionMode ? "running" : null);
  const isRunActive = resolvedStatus === "running" || resolvedStatus === "pending";
  const forkUnavailable = hasSnapshot === false || !run?.commit_sha;
  const forkDisabled = isHistoricalMode && (isRunActive || forkUnavailable);
  const forkTitle = isRunActive
    ? "Wait for the run to finish before forking"
    : forkUnavailable
      ? "Snapshot unavailable"
      : undefined;
  const totalCost = metrics?.total_cost_usd ?? run?.total_cost_usd;
  const totalTokens = metrics?.total_tokens ?? run?.total_tokens;
  const canShowTabs = isWorkflowMode && Boolean(onTabChange);
  const defaultRunControl = isWorkflowMode && onRun ? (
    <Button variant="primary" onClick={onRun}>
      Run
    </Button>
  ) : null;

  return (
    <header
      className="flex h-[var(--header-height)] items-center gap-4 border-b border-border-subtle px-4"
      style={{ gridColumn: "1 / -1", gridRow: "1" }}
    >
      <div className="flex min-w-0 flex-1 items-center gap-3">
        {leadingContent}
        <div className="min-w-0">
          <div className="truncate text-lg font-medium text-heading">{workflowName}</div>
        </div>
        {isHistoricalMode ? (
          <div className="flex items-center gap-1.5 rounded bg-[var(--accent-2)] px-2 py-1 text-[11px] font-medium text-[var(--interactive-default)]">
            Read-only review
          </div>
        ) : null}
        {resolvedStatus ? (
          <span
            className={cn(
              "rounded px-2 py-0.5 text-xs font-medium",
              isHistoricalMode
                ? "bg-neutral-3 text-muted"
                : "bg-[var(--surface-raised)] text-[var(--text-primary)]",
            )}
          >
            {formatStatus(resolvedStatus)}
          </span>
        ) : null}
      </div>

      {canShowTabs ? (
        <div className="flex items-center">
          <Tabs value={activeTab} onValueChange={onTabChange}>
            <TabsList variant="contained">
              <TabsTrigger value="canvas">Canvas</TabsTrigger>
              <TabsTrigger value="yaml">YAML</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      ) : null}

      <div className="flex flex-1 items-center justify-end gap-2">
        {(isHistoricalMode || isExecutionMode) ? (
          <>
            <MetricCard label="Total Cost" value={formatCost(totalCost)} />
            <MetricCard label="Tokens" value={formatTokens(totalTokens)} />
          </>
        ) : null}

        {isWorkflowMode && isDirty ? (
          <span
            className="h-2 w-2 rounded-full bg-interactive-default"
            aria-label="unsaved indicator"
          />
        ) : null}

        {isWorkflowMode && onSave ? (
          <Button variant={isDirty ? "primary" : "ghost"} size="sm" onClick={onSave}>
            Save
          </Button>
        ) : null}

        {isWorkflowMode ? (runControl ?? defaultRunControl) : null}

        {isHistoricalMode ? (
          <Button
            variant="ghost"
            disabled={forkDisabled}
            onClick={onFork}
            aria-label="Fork"
            title={forkTitle}
          >
            Fork
          </Button>
        ) : null}

        {isHistoricalMode && run?.workflow_id && onOpenWorkflow ? (
          <Button
            className="h-9 px-4 bg-[var(--interactive-default)] text-on-accent hover:bg-[var(--interactive-hover)]"
            onClick={onOpenWorkflow}
          >
            Open Workflow
          </Button>
        ) : null}
      </div>
    </header>
  );
}

export const Component = WorkflowSurfaceTopbar;

export default WorkflowSurfaceTopbar;
