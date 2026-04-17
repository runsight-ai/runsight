import { useMemo, useState } from "react";
import type { ContextAuditEventV1 } from "@runsight/shared/zod";
import { cn } from "@runsight/ui/utils";
import {
  EMPTY_CONTEXT_AUDIT_EVENTS,
  contextAuditRowsFromEvents,
  selectRunEvents,
  useContextAuditStore,
  type ContextAuditTableRow,
} from "@/store/contextAudit";

export interface ContextAuditPanelProps {
  runId: string | undefined;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
  fetchNextPage?: () => Promise<unknown>;
  hasNextPage?: boolean;
}

export interface ContextInspectorTabProps {
  events: ContextAuditEventV1[];
}

export interface ContextAccessBadgeProps {
  access: string | null | undefined;
}

export interface ContextResolutionBadgeProps {
  warningCount: number;
  deniedCount: number;
}

const PAGE_SIZE = 100;

export function ContextAuditPanel({
  runId,
  selectedNodeId,
  onSelectNode,
  fetchNextPage,
  hasNextPage,
}: ContextAuditPanelProps) {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const events = useContextAuditStore((state) =>
    runId ? selectRunEvents(runId)(state) : EMPTY_CONTEXT_AUDIT_EVENTS,
  );
  const rows = useMemo(() => contextAuditRowsFromEvents(events), [events]);
  const visibleRows = rows.slice(0, visibleCount);
  const canShowMoreLocal = rows.length > visibleCount;
  const canLoadMore = canShowMoreLocal || Boolean(hasNextPage);

  const loadMore = async () => {
    if (canShowMoreLocal) {
      setVisibleCount((count) => count + PAGE_SIZE);
      return;
    }
    await fetchNextPage?.();
  };

  if (!runId) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted">
        Select a run to inspect audit records.
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted">
        No context audit records captured for this run yet.
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="overflow-auto flex-1">
        <table className="min-w-full table-fixed text-left text-xs">
          <thead className="sticky top-0 bg-surface-secondary text-[11px] uppercase text-muted">
            <tr>
              <th className="w-[120px] px-3 py-2 font-medium">Node</th>
              <th className="w-[120px] px-3 py-2 font-medium">Input</th>
              <th className="w-[220px] px-3 py-2 font-medium">Reference</th>
              <th className="w-[96px] px-3 py-2 font-medium">Status</th>
              <th className="w-[96px] px-3 py-2 font-medium">Severity</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => (
              <ContextAuditRow
                key={row.id}
                row={row}
                selected={row.nodeId === selectedNodeId}
                onSelectNode={onSelectNode}
              />
            ))}
          </tbody>
        </table>
      </div>
      {canLoadMore ? (
        <div className="border-t border-border-subtle p-2">
          <button
            type="button"
            className="rounded-md border border-border-subtle px-3 py-1 text-xs text-primary hover:bg-surface-tertiary"
            onClick={() => void loadMore()}
          >
            Load more
          </button>
        </div>
      ) : null}
    </div>
  );
}

function ContextAuditRow({
  row,
  selected,
  onSelectNode,
}: {
  row: ContextAuditTableRow;
  selected: boolean;
  onSelectNode: (nodeId: string) => void;
}) {
  const activate = () => onSelectNode(row.nodeId);
  return (
    <tr
      tabIndex={0}
      role="button"
      aria-label={`Open context audit for ${row.nodeId}`}
      onClick={activate}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          activate();
        }
      }}
      className={cn(
        "cursor-pointer border-b border-border-subtle hover:bg-surface-tertiary",
        selected && "bg-surface-tertiary",
      )}
    >
      <td className="truncate px-3 py-2 font-mono text-primary">{row.nodeId}</td>
      <td className="truncate px-3 py-2">{row.inputName ?? "all"}</td>
      <td className="break-all px-3 py-2 font-mono text-muted">{row.fromRef ?? row.access}</td>
      <td className="px-3 py-2">
        <span className={resolutionClass(row.status)}>{row.status}</span>
      </td>
      <td className="px-3 py-2">
        <span className={severityClass(row.severity)}>{row.severity}</span>
      </td>
    </tr>
  );
}

export function ContextInspectorTab({ events }: ContextInspectorTabProps) {
  if (events.length === 0) {
    return (
      <div className="rounded-md border border-[var(--border-default)] bg-[var(--surface-primary)] p-3 text-sm text-[var(--text-muted)]">
        No context reads captured for this node.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {events.map((event) => (
        <section
          key={`${event.run_id}:${event.sequence ?? event.emitted_at}:${event.node_id}`}
          className="border-b border-[var(--border-default)] pb-3 last:border-b-0"
        >
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="font-mono text-[11px] uppercase text-[var(--text-muted)]">
              {event.block_type}
            </span>
            <ContextAccessBadge access={event.access} />
            <ContextResolutionBadge warningCount={event.warning_count ?? 0} deniedCount={event.denied_count ?? 0} />
            <span className="text-[11px] text-[var(--text-muted)]">
              {event.resolved_count ?? 0} resolved · {event.warning_count ?? 0} warning · {event.denied_count ?? 0} denied
            </span>
          </div>
          <table className="w-full table-fixed text-left text-xs">
            <thead className="text-[11px] uppercase text-[var(--text-muted)]">
              <tr>
                <th className="w-[28%] py-1 pr-2 font-medium">Input</th>
                <th className="w-[34%] py-1 pr-2 font-medium">Reference</th>
                <th className="w-[18%] py-1 pr-2 font-medium">Status</th>
                <th className="w-[20%] py-1 font-medium">Preview</th>
              </tr>
            </thead>
            <tbody>
              {(event.records ?? []).map((record, index) => (
                <tr key={`${record.input_name ?? "record"}:${index}`} className="border-t border-border-subtle align-top">
                  <td className="truncate py-1.5 pr-2 font-medium text-[var(--text-primary)]">
                    {record.input_name ?? "all access"}
                  </td>
                  <td className="break-all py-1.5 pr-2 font-mono text-[var(--text-muted)]">
                    {record.from_ref ?? record.reason ?? event.access}
                  </td>
                  <td className="py-1.5 pr-2">
                    <div className="flex flex-col gap-0.5">
                      <span className={resolutionClass(record.status)}>{record.status}</span>
                      <span className={severityClass(record.severity)}>{record.severity}</span>
                    </div>
                  </td>
                  <td className="break-all py-1.5 text-[var(--text-secondary)]">
                    {record.preview ?? "No preview"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
    </div>
  );
}

export function ContextAccessBadge({ access }: ContextAccessBadgeProps) {
  const label = access === "all" ? "Access all" : "Access declared";
  const tone =
    access === "all"
      ? "border-[var(--warning-9)]/40 bg-warning-3 text-[var(--warning-11)]"
      : "border-[var(--info-9)]/40 bg-info-3 text-[var(--info-11)]";
  return (
    <span className={cn("inline-flex min-w-[84px] items-center rounded-md border px-2 py-0.5 text-[11px] font-medium", tone)}>
      {label}
    </span>
  );
}

export function ContextResolutionBadge({
  warningCount,
  deniedCount,
}: ContextResolutionBadgeProps) {
  if (deniedCount > 0) {
    return (
      <span className="inline-flex h-[22px] min-w-[72px] items-center rounded-md border border-[var(--danger-9)]/40 bg-danger-3 px-2 text-[11px] font-medium text-[var(--danger-9)]">
        Denied {deniedCount}
      </span>
    );
  }
  if (warningCount > 0) {
    return (
      <span className="inline-flex h-[22px] min-w-[72px] items-center rounded-md border border-[var(--warning-9)]/40 bg-warning-3 px-2 text-[11px] font-medium text-[var(--warning-11)]">
        Warning {warningCount}
      </span>
    );
  }
  return (
    <span className="inline-flex h-[22px] min-w-[72px] items-center rounded-md border border-[var(--success-9)]/40 bg-success-3 px-2 text-[11px] font-medium text-[var(--success-11)]">
      Resolved
    </span>
  );
}

export function useNodeContextEvents(runId: string | undefined, nodeId: string | undefined) {
  const events = useContextAuditStore((state) =>
    runId ? selectRunEvents(runId)(state) : EMPTY_CONTEXT_AUDIT_EVENTS,
  );
  return useMemo(
    () => (nodeId ? events.filter((event) => event.node_id === nodeId) : EMPTY_CONTEXT_AUDIT_EVENTS),
    [events, nodeId],
  );
}

function resolutionClass(status: string) {
  if (status === "denied") return "text-[var(--danger-9)]";
  if (status === "missing") return "text-[var(--warning-11)]";
  return "text-[var(--success-11)]";
}

function severityClass(severity: string) {
  if (severity === "error") return "text-[var(--danger-9)]";
  if (severity === "warn") return "text-[var(--warning-11)]";
  if (severity === "allow") return "text-[var(--success-11)]";
  return "text-[var(--success-11)]";
}
