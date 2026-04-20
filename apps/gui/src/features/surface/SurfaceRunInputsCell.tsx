import { useId, useState } from "react";
import { Badge } from "@runsight/ui/badge";
import { Button } from "@runsight/ui/button";
import { cn } from "@runsight/ui/utils";
import type { RunResponse } from "@runsight/shared/zod";

const clipboardWriteTextAtLoad = navigator.clipboard?.writeText;

type WorkflowInputSnapshotEntry = {
  type?: string;
  sensitive?: boolean;
  source?: string;
  value?: unknown;
};

type SurfaceRunInputsCellProps = {
  run: RunResponse;
  onRerun?: (run: RunResponse) => void;
};

type WorkflowInputSummary = {
  name: string;
  entry: WorkflowInputSnapshotEntry;
  preview: string;
};

function isWorkflowInputSnapshotEntry(value: unknown): value is WorkflowInputSnapshotEntry {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function getWorkflowInputSummaries(
  workflowInputs: RunResponse["workflow_inputs"],
): WorkflowInputSummary[] {
  if (!workflowInputs || typeof workflowInputs !== "object" || Array.isArray(workflowInputs)) {
    return [];
  }

  return Object.entries(workflowInputs)
    .map(([name, entry]) => {
      if (!isWorkflowInputSnapshotEntry(entry)) {
        return null;
      }

      return {
        name,
        entry,
        preview: formatInputPreview(entry),
      };
    })
    .filter((summary): summary is WorkflowInputSummary => summary !== null);
}

function formatInputPreview(entry: WorkflowInputSnapshotEntry) {
  if (entry.sensitive) {
    return "sensitive";
  }

  const value = entry.value;

  if (value === null) {
    return "null";
  }

  if (typeof value === "string") {
    return truncatePreview(value);
  }

  if (typeof value === "number" || typeof value === "boolean" || typeof value === "bigint") {
    return String(value);
  }

  if (Array.isArray(value)) {
    return `array(${value.length})`;
  }

  if (value && typeof value === "object") {
    return "JSON";
  }

  return "omitted";
}

function truncatePreview(value: string, maxLength = 32) {
  if (value.length <= maxLength) {
    return value;
  }

  return `${value.slice(0, maxLength - 1)}…`;
}

function stringifyJson(value: unknown) {
  const formatted = JSON.stringify(
    value,
    (_, current) => (typeof current === "bigint" ? current.toString() : current),
    2,
  );

  return typeof formatted === "string" ? formatted : "null";
}

function formatStoredValue(value: unknown) {
  return stringifyJson(value);
}

function getSafeWorkflowInputs(summaries: WorkflowInputSummary[]) {
  return Object.fromEntries(
    summaries
      .filter((summary) => !summary.entry.sensitive)
      .map((summary) => [summary.name, summary.entry.value]),
  );
}

function InputSummaryChip({
  name,
  preview,
}: {
  name: string;
  preview: string;
}) {
  return (
    <span className="inline-flex max-w-full items-center gap-1 overflow-hidden rounded-full border border-border-subtle bg-surface-secondary px-1.5 py-0.5 text-2xs leading-none">
      <Badge variant="outline" className="shrink-0 border-0 px-0 py-0 text-inherit uppercase">
        {name}
      </Badge>
      <span className="min-w-0 truncate text-secondary">{preview}</span>
    </span>
  );
}

export function SurfaceRunInputsCell({
  run,
  onRerun,
}: SurfaceRunInputsCellProps) {
  const panelId = useId();
  const [isOpen, setIsOpen] = useState(false);
  const summaries = getWorkflowInputSummaries(run.workflow_inputs);

  const safeInputs = getSafeWorkflowInputs(summaries);
  const safeJson = stringifyJson(safeInputs);
  const previewSummaries = summaries.slice(0, 2);
  const remainingCount = summaries.length - previewSummaries.length;
  const triggerLabel =
    run.run_number != null
      ? `View inputs for run #${run.run_number}`
      : `View inputs for run ${run.id}`;
  const rerunLabel =
    run.run_number != null ? `Rerun run #${run.run_number}` : `Rerun run ${run.id}`;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {summaries.length > 0 ? (
          <Button
            type="button"
            variant="ghost"
            size="xs"
            aria-label={triggerLabel}
            aria-expanded={isOpen}
            aria-controls={panelId}
            className={cn(
              "h-6 max-w-full justify-start overflow-hidden px-0 text-left font-mono normal-case tracking-normal",
              "hover:bg-transparent hover:text-primary",
            )}
            onClick={(event) => {
              event.stopPropagation();
              setIsOpen((current) => !current);
            }}
          >
            <span className="inline-flex max-w-full items-center gap-1 overflow-hidden">
              {isOpen ? (
                <span className="text-muted">Inputs open</span>
              ) : (
                <>
                  {previewSummaries.map((summary) => (
                    <InputSummaryChip
                      key={summary.name}
                      name={summary.name}
                      preview={summary.preview}
                    />
                  ))}
                  {remainingCount > 0 ? <span className="shrink-0 text-muted">+{remainingCount}</span> : null}
                </>
              )}
            </span>
          </Button>
        ) : (
          <span className="text-muted">No inputs</span>
        )}

        {onRerun ? (
          <Button
            type="button"
            variant="ghost"
            size="xs"
            aria-label={rerunLabel}
            className="h-6 px-2 text-2xs font-medium uppercase tracking-wide"
            onClick={(event) => {
              event.stopPropagation();
              onRerun(run);
            }}
          >
            Rerun
          </Button>
        ) : null}
      </div>

      {summaries.length > 0 && isOpen ? (
        <div
          id={panelId}
          role="region"
          aria-label="Run input details"
          onClick={(event) => event.stopPropagation()}
          className="w-[min(26rem,100%)] space-y-4 rounded-md border border-border-subtle bg-surface-primary p-3 shadow-[var(--elevation-overlay-shadow)]"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-medium text-heading">Run inputs</p>
              <p className="text-xs text-muted">Stored snapshot for this run</p>
            </div>
            <button
              type="button"
              className="inline-flex h-6 items-center justify-center gap-1 rounded-sm border border-transparent bg-surface-tertiary px-2 text-2xs font-medium leading-tight tracking-wide text-primary hover:bg-surface-hover hover:border-border-hover active:bg-surface-active"
              onClick={(event) => {
                event.stopPropagation();
                void clipboardWriteTextAtLoad?.call(navigator.clipboard, safeJson);
              }}
            >
              Copy
            </button>
          </div>

          <div className="space-y-3">
            {summaries.map((summary) => (
              <div key={summary.name} className="space-y-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className="border-border-default text-secondary">
                    {summary.name}
                  </Badge>
                  {summary.entry.source ? (
                    <span className="text-2xs uppercase tracking-wider text-muted">
                      {summary.entry.source}
                    </span>
                  ) : null}
                  {summary.entry.type ? (
                    <span className="text-2xs uppercase tracking-wider text-muted">
                      {summary.entry.type}
                    </span>
                  ) : null}
                  {summary.entry.sensitive ? (
                    <span className="text-2xs uppercase tracking-wider text-warning-11">
                      Hidden
                    </span>
                  ) : null}
                </div>
                {summary.entry.sensitive ? (
                  <p className="text-sm text-secondary">Sensitive input omitted.</p>
                ) : (
                  <pre className="overflow-auto rounded-md border border-border-subtle bg-surface-secondary p-3 font-mono text-2xs leading-5 text-primary">
                    {formatStoredValue(summary.entry.value)}
                  </pre>
                )}
              </div>
            ))}
          </div>

        </div>
      ) : null}
    </div>
  );
}
