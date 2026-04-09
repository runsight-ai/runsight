import { useState } from "react";
import type { Node } from "@xyflow/react";

import { Button } from "@runsight/ui/button";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { cn } from "@runsight/ui/utils";
import { formatDuration } from "@/utils/formatting";
import { CheckCircle, XCircle, Clock, X } from "lucide-react";
type InspectorNodeData = Record<string, unknown> & {
  name: string;
  status?: string;
  soulRef?: string;
  model?: string;
  executionCost?: number;
  duration?: number;
  tokens?: { input?: number; output?: number; total?: number };
  error?: string | null;
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface RunInspectorPanelProps {
  selectedNode: Node<InspectorNodeData> | null;
  onClose: () => void;
  trigger?: "single-click" | "double-click";
}

// ---------------------------------------------------------------------------
// Status helpers
// ---------------------------------------------------------------------------

function statusIcon(status: string) {
  if (status === "completed") return <CheckCircle className="w-4 h-4 text-[var(--success-9)]" />;
  if (status === "failed") return <XCircle className="w-4 h-4 text-[var(--danger-9)]" />;
  return <Clock className="w-4 h-4 text-[var(--text-muted)]" />;
}

function statusLabel(status: string) {
  if (status === "completed") return "Completed";
  if (status === "failed") return "Failed";
  if (status === "pending") return "Pending";
  return "Idle";
}

function statusColorClass(status: string) {
  if (status === "completed") return "text-[var(--success-9)]";
  if (status === "failed") return "text-[var(--danger-9)]";
  return "text-[var(--text-muted)]";
}

function bannerClass(status: string) {
  if (status === "completed") return "bg-success-3 border-[var(--success-9)]/30";
  if (status === "failed") return "bg-danger-3 border-[var(--danger-9)]/30";
  return "bg-[var(--surface-primary)] border-[var(--border-default)]";
}

function badgeVariant(status: string): "success" | "error" | "pending" {
  if (status === "completed") return "success";
  if (status === "failed") return "error";
  return "pending";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RunInspectorPanel({ selectedNode, onClose, trigger = "double-click" }: RunInspectorPanelProps) {
  const [activeTab, setActiveTab] = useState<"overview" | "execution">("execution");

  if (!selectedNode) return null;

  const d = selectedNode.data;
  const status = d.status || "idle";

  return (
    <aside data-testid="right-inspector" data-trigger={trigger} className="w-[320px] min-w-[280px] max-w-[480px] bg-[var(--surface-secondary)] border-l border-[var(--border-default)] flex flex-col z-50 animate-in slide-in-from-right duration-200">
      {/* Header */}
      <div className="h-12 px-3 border-b border-[var(--border-default)] flex items-center justify-between shrink-0">
        <h2 className="text-base font-medium text-[var(--text-primary)] truncate">{d.name}</h2>
        <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close inspector" className="w-8 h-8 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-raised)]">
          <X className="w-4 h-4" />
        </Button>
      </div>

      {/* Tab Bar */}
      <div role="tablist" aria-label="Inspector tabs" className="h-9 flex items-center px-2 border-b border-[var(--border-default)] gap-1 shrink-0 overflow-x-auto">
        {(["execution", "overview"] as const).map((tab) => (
          <button key={tab} role="tab" aria-selected={activeTab === tab} aria-controls={`inspector-${tab}-panel`} id={`inspector-${tab}-tab`} onClick={() => setActiveTab(tab)} className={cn("h-full px-3 text-[12px] font-medium whitespace-nowrap transition-colors border-b-2", activeTab === tab ? "text-[var(--text-primary)] border-[var(--interactive-default)]" : "text-[var(--text-muted)] hover:text-[var(--text-primary)] border-transparent")}>
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-3 min-h-0">
        {activeTab === "execution" && (
          <div role="tabpanel" id="inspector-execution-panel" aria-labelledby="inspector-execution-tab" className="space-y-4">
            <div className={cn("mb-4 p-3 rounded-md border", bannerClass(status))}>
              <div className="flex items-center gap-2 mb-2">
                {statusIcon(status)}
                <span className={cn("text-sm font-medium", statusColorClass(status))}>{statusLabel(status)}</span>
              </div>
              {d.duration && <div className="font-mono text-xs text-[var(--text-muted)]">Duration: {formatDuration(d.duration)}</div>}
            </div>
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)] mb-2">Cost</label>
              <div className="flex items-center justify-between p-2 rounded-md bg-[var(--surface-primary)] border border-[var(--border-default)]">
                <span className="font-mono text-sm text-[var(--text-primary)]">${(d.executionCost || 0).toFixed(3)}</span>
              </div>
            </div>
            {d.tokens && (
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)] mb-2">Token Usage</label>
                <div className="p-3 rounded-md bg-[var(--surface-primary)] border border-[var(--border-default)] space-y-2">
                  {d.tokens.input !== undefined && (
                    <div>
                      <div className="flex justify-between text-xs mb-1"><span className="text-[var(--text-muted)]">Prompt</span><span className="font-mono text-[var(--text-primary)]">{d.tokens.input.toLocaleString()}</span></div>
                      <div className="h-1.5 bg-[var(--border-default)] rounded-full overflow-hidden"><div className="h-full bg-[var(--interactive-default)] rounded-full" style={{ width: `${((d.tokens.input || 0) / (d.tokens.total || 1)) * 100}%` }} /></div>
                    </div>
                  )}
                  {d.tokens.output !== undefined && (
                    <div>
                      <div className="flex justify-between text-xs mb-1"><span className="text-[var(--text-muted)]">Completion</span><span className="font-mono text-[var(--text-primary)]">{d.tokens.output.toLocaleString()}</span></div>
                      <div className="h-1.5 bg-[var(--border-default)] rounded-full overflow-hidden"><div className="h-full bg-[var(--interactive-default)] rounded-full" style={{ width: `${((d.tokens.output || 0) / (d.tokens.total || 1)) * 100}%` }} /></div>
                    </div>
                  )}
                  <div className="flex justify-between text-xs pt-1 border-t border-[var(--border-default)]"><span className="text-[var(--text-muted)]">Total</span><span className="font-mono text-[var(--text-primary)]">{d.tokens.total?.toLocaleString()} tokens</span></div>
                </div>
              </div>
            )}
            {status === "failed" && d.error && (
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)] mb-2">Error</label>
                <div className="p-3 rounded-md bg-danger-3 border border-[var(--danger-9)]/30 font-mono text-xs text-[var(--danger-9)] leading-relaxed">{d.error}</div>
              </div>
            )}
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)] mb-2">Configuration</label>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-[var(--text-muted)]">Soul</span><span className="text-[var(--text-primary)]">{d.soulRef || "\u2014"}</span></div>
                <div className="flex justify-between"><span className="text-[var(--text-muted)]">Model</span><span className="text-[var(--text-primary)]">{d.model || "\u2014"}</span></div>
              </div>
            </div>
          </div>
        )}
        {activeTab === "overview" && (
          <div role="tabpanel" id="inspector-overview-panel" aria-labelledby="inspector-overview-tab" className="space-y-4">
            <div><label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)] mb-2">Name</label><div className="p-2 rounded-md bg-[var(--surface-primary)] border border-[var(--border-default)] text-sm text-[var(--text-primary)]">{d.name}</div></div>
            <div><label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)] mb-2">Status</label><StatusBadge status={badgeVariant(status)} label={statusLabel(status)} /></div>
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)] mb-2">Configuration</label>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-[var(--text-muted)]">Soul</span><span className="text-[var(--text-primary)]">{d.soulRef || "\u2014"}</span></div>
                <div className="flex justify-between"><span className="text-[var(--text-muted)]">Model</span><span className="text-[var(--text-primary)]">{d.model || "\u2014"}</span></div>
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
