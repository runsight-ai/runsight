import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router";
import { useProviders, useAppSettings } from "@/queries/settings";
import { useWorkflows } from "@/queries/workflows";
import { useDashboardSummary, useRecentRuns } from "@/queries/dashboard";
import { Zap, Upload, Plus, Filter, MoreHorizontal, Play, DollarSign, Activity } from "lucide-react";
import { DataTable, type Column } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { CostDisplay } from "@/components/shared/CostDisplay";
import { Button } from "@/components/ui/button";
import { NewWorkflowModal } from "@/features/workflows/NewWorkflowModal";
import type { WorkflowResponse } from "@/types/schemas/workflows";
import type { RunResponse } from "@/types/schemas/runs";

function getWorkflowIcon(name: string) {
  const iconClass = "w-5 h-5";
  const lower = name.toLowerCase();
  if (lower.includes("code") || lower.includes("review")) {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="2" y="3" width="20" height="6" rx="2"/>
        <rect x="2" y="15" width="20" height="6" rx="2"/>
      </svg>
    );
  }
  if (lower.includes("moderation") || lower.includes("content")) {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M12 2L2 7l10 5 10-5-10-5z"/>
        <path d="M2 17l10 5 10-5"/>
        <path d="M2 12l10 5 10-5"/>
      </svg>
    );
  }
  if (lower.includes("report") || lower.includes("daily")) {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="12" cy="12" r="10"/>
        <path d="M8 12l3 3 5-5"/>
      </svg>
    );
  }
  if (lower.includes("email") || lower.includes("classifier")) {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="3" y="4" width="18" height="18" rx="2"/>
        <line x1="16" y1="2" x2="16" y2="6"/>
        <line x1="8" y1="2" x2="8" y2="6"/>
        <line x1="3" y1="10" x2="21" y2="10"/>
      </svg>
    );
  }
  if (lower.includes("support") || lower.includes("ticket")) {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z"/>
      </svg>
    );
  }
  if (lower.includes("sync") || lower.includes("data")) {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="12" cy="12" r="10"/>
        <line x1="15" y1="9" x2="9" y2="15"/>
        <line x1="9" y1="9" x2="15" y2="15"/>
      </svg>
    );
  }
  return (
    <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="3" y="3" width="7" height="7"/>
      <rect x="14" y="3" width="7" height="7"/>
      <rect x="14" y="14" width="7" height="7"/>
      <rect x="3" y="14" width="7" height="7"/>
    </svg>
  );
}

function getWorkflowIconBg(name: string) {
  const lower = name.toLowerCase();
  if (lower.includes("code") || lower.includes("review")) return "bg-[rgba(94,106,210,0.12)] text-[#5E6AD2]";
  if (lower.includes("moderation") || lower.includes("content")) return "bg-[rgba(245,166,35,0.12)] text-[#F5A623]";
  if (lower.includes("report") || lower.includes("daily")) return "bg-[rgba(40,167,69,0.12)] text-[#28A745]";
  if (lower.includes("email") || lower.includes("classifier")) return "bg-[rgba(94,106,210,0.12)] text-[#5E6AD2]";
  if (lower.includes("support") || lower.includes("ticket")) return "bg-[#22222A] text-[#9292A0]";
  if (lower.includes("sync") || lower.includes("data")) return "bg-[rgba(229,57,53,0.12)] text-[#E53935]";
  return "bg-[rgba(94,106,210,0.12)] text-[#5E6AD2]";
}

function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return "—";
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins < 60) return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
  const hrs = Math.floor(mins / 60);
  const remainingMins = mins % 60;
  return remainingMins > 0 ? `${hrs}h ${remainingMins}m` : `${hrs}h`;
}

function getTimeAgo(date: string): string {
  const now = new Date();
  const then = new Date(date);
  const diffMs = now.getTime() - then.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  const diffWeeks = Math.floor(diffDays / 7);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins} min ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? "s" : ""} ago`;
  if (diffWeeks < 4) return `${diffWeeks} week${diffWeeks > 1 ? "s" : ""} ago`;
  return then.toLocaleDateString();
}

function PopulatedDashboard({ onNewWorkflow }: { onNewWorkflow: () => void }) {
  const { data: dashboardData, isLoading: dashboardLoading } = useDashboardSummary();
  const { data: workflowsData, isLoading: workflowsLoading } = useWorkflows();
  const { data: recentRunsData, isLoading: runsLoading } = useRecentRuns(6);

  const isLoading = dashboardLoading || workflowsLoading || runsLoading;

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="flex items-center gap-2 text-muted-foreground">
          <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
          Loading dashboard...
        </div>
      </div>
    );
  }

  const summary = dashboardData || {
    active_runs: 0,
    completed_runs: 0,
    total_cost_usd: 0,
    failed_runs: 0,
    total_runs: 0,
  };

  const workflows = workflowsData?.items || [];
  const recentRuns = recentRunsData?.items || [];

  const workflowColumns: Column[] = [
    {
      key: "name",
      header: "Workflow Name",
      width: "2fr",
      render: (row) => {
        const workflow = row as WorkflowResponse;
        const name = workflow.name || "Untitled";
        const updatedAt = workflow.updated_at;
        const createdAt = workflow.created_at;
        return (
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-md flex items-center justify-center ${getWorkflowIconBg(name)}`}>
              {getWorkflowIcon(name)}
            </div>
            <div>
              <div className="text-sm font-medium text-foreground">{name}</div>
              <div className="text-xs text-muted-foreground">
                Last edited {getTimeAgo(updatedAt || createdAt || new Date().toISOString())}
              </div>
            </div>
          </div>
        );
      },
    },
    {
      key: "status",
      header: "Status",
      width: "100px",
      render: (row) => {
        const workflow = row as WorkflowResponse;
        const status = workflow.status || "idle";
        const variant = status === "running" ? "running" : status === "completed" ? "success" : status === "failed" ? "error" : "pending";
        return (
          <div className="flex justify-center">
            <StatusBadge status={variant} label={status.charAt(0).toUpperCase() + status.slice(1)} />
          </div>
        );
      },
    },
    {
      key: "duration",
      header: "Duration",
      width: "120px",
      render: (row) => {
        const workflow = row as WorkflowResponse;
        const duration = workflow.last_run_duration ?? 0;
        return (
          <div className="text-right font-mono text-sm text-muted-foreground">
            {formatDuration(duration)}
          </div>
        );
      },
    },
    {
      key: "cost",
      header: "Cost",
      width: "100px",
      render: (row) => {
        const workflow = row as WorkflowResponse;
        const cost = workflow.last_run_cost_usd ?? 0;
        const completedAt = workflow.last_run_completed_at;
        return (
          <div className="text-right font-mono text-sm text-muted-foreground">
            <CostDisplay cost={cost} isEstimate={!completedAt} />
          </div>
        );
      },
    },
    {
      key: "agents",
      header: "Agents",
      width: "100px",
      render: (row) => {
        const workflow = row as WorkflowResponse;
        const count = workflow.step_count ?? workflow.block_count ?? Object.keys(workflow.blocks || {}).length;
        return (
          <div className="text-center text-sm text-muted-foreground">{count}</div>
        );
      },
    },
    {
      key: "actions",
      header: "",
      width: "48px",
      render: (row) => {
        const workflow = row as WorkflowResponse;
        return (
          <div className="flex justify-center">
            <Link to={`/workflows/${workflow.id}`}>
              <Button variant="ghost" size="icon-sm" className="h-8 w-8">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        );
      },
    },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-6">
      {/* Quick Actions Row */}
      <div className="flex items-center gap-3 mb-8">
        <Button
          variant="outline"
          className="h-9 px-4 border-[#3F3F4A] bg-transparent hover:bg-[#22222A] text-foreground"
          disabled
        >
          <Zap className="w-4 h-4 mr-2" strokeWidth={1.5} />
          Generate with AI
        </Button>
        <Button
          variant="outline"
          className="h-9 px-4 border-[#3F3F4A] bg-transparent hover:bg-[#22222A] text-foreground"
          onClick={onNewWorkflow}
        >
          <Plus className="w-4 h-4 mr-2" strokeWidth={1.5} />
          New Workflow
        </Button>
        <Button
          variant="outline"
          className="h-9 px-4 border-[#3F3F4A] bg-transparent hover:bg-[#22222A] text-foreground"
          disabled
        >
          <Upload className="w-4 h-4 mr-2" strokeWidth={1.5} />
          Import YAML
        </Button>
      </div>

      {/* System Health Summary */}
      <div className="mb-6 flex items-center gap-6">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-[#28A745]" />
          <span className="text-sm text-muted-foreground">All Systems Operational</span>
        </div>
        <div className="text-sm text-[#5E5E6B]">|</div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Active Runs:</span>
          <span className="text-sm font-medium text-[#00E5FF]">{summary.active_runs}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Queued:</span>
          <span className="text-sm font-medium text-foreground">0</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Completed (24h):</span>
          <span className="text-sm font-medium text-[#28A745]">{summary.completed_runs}</span>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <div className="bg-[#16161C] border border-[#2D2D35] rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Active Runs</span>
            <Play className="w-4 h-4 text-[#00E5FF]" />
          </div>
          <div className="text-2xl font-semibold text-foreground">{summary.active_runs}</div>
        </div>
        <div className="bg-[#16161C] border border-[#2D2D35] rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Completed</span>
            <Activity className="w-4 h-4 text-[#28A745]" />
          </div>
          <div className="text-2xl font-semibold text-foreground">{summary.completed_runs}</div>
        </div>
        <div className="bg-[#16161C] border border-[#2D2D35] rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Total Cost</span>
            <DollarSign className="w-4 h-4 text-muted-foreground" />
          </div>
          <div className="text-2xl font-semibold text-foreground">
            ${summary.total_cost_usd.toFixed(2)}
          </div>
        </div>
        <div className="bg-[#16161C] border border-[#2D2D35] rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">System Health</span>
            <div className="w-2 h-2 rounded-full bg-[#28A745]" />
          </div>
          <div className="text-2xl font-semibold text-[#28A745]">Healthy</div>
        </div>
      </div>

      {/* Active Workflows Section */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-medium text-foreground tracking-tight">Active Workflows</h2>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="h-9 px-3 border-[#2D2D35] text-muted-foreground hover:text-foreground hover:border-[#3F3F4A]"
            >
              <Filter className="w-4 h-4 mr-2" />
              Filter
            </Button>
          </div>
        </div>

        <DataTable
          columns={workflowColumns}
          data={workflows.map(w => w as Record<string, unknown>)}
          searchable
          searchPlaceholder="Search workflows..."
          className="bg-[#16161C] border border-[#2D2D35] rounded-lg overflow-hidden"
        />
      </div>

      {/* Recent Runs Summary */}
      {recentRuns.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-medium text-foreground tracking-tight">Recent Runs</h2>
            <Link to="/runs" className="text-sm text-[#5E6AD2] hover:text-[#717EE3] transition-colors">
              View All
            </Link>
          </div>

          <div className="grid grid-cols-3 gap-4">
            {recentRuns.slice(0, 3).map((run: RunResponse) => {
              const status = run.status || "unknown";
              const variant = status === "success" ? "success" : status === "failed" ? "error" : status === "running" ? "running" : "pending";
              const statusLabel = status.charAt(0).toUpperCase() + status.slice(1);
              const workflowName = run.workflow_name || "Unknown Workflow";
              const nodeSummary = run.node_summary;
              const agents = nodeSummary ? Object.keys(nodeSummary).length : 0;

              return (
                <Link
                  key={run.id}
                  to={`/runs/${run.id}`}
                  className="bg-[#16161C] border border-[#2D2D35] rounded-lg p-6 hover:border-[#3F3F4A] hover:bg-[#22222A] transition-all cursor-pointer block no-underline"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className={`w-1.5 h-1.5 rounded-full ${variant === "success" ? "bg-[#28A745]" : variant === "error" ? "bg-[#E53935]" : variant === "running" ? "bg-[#00E5FF]" : "bg-[#9292A0]"}`} />
                      <span className={`text-xs font-medium ${variant === "success" ? "text-[#28A745]" : variant === "error" ? "text-[#E53935]" : variant === "running" ? "text-[#00E5FF]" : "text-muted-foreground"}`}>
                        {statusLabel}
                      </span>
                    </div>
                    <span className="text-xs text-[#5E5E6B]">{getTimeAgo(new Date(run.created_at).toISOString())}</span>
                  </div>
                  <div className="text-sm font-medium text-foreground mb-1">{workflowName}</div>
                  <div className="text-xs text-muted-foreground mb-3">Run #{String(run.id).slice(-4)}</div>
                  <div className="flex items-center justify-between pt-3 border-t border-[#2D2D35]">
                    <div className="flex items-center gap-3">
                      <div className="flex -space-x-1">
                        {Array.from({ length: Math.min(agents, 3) }).map((_, i) => (
                          <div
                            key={i}
                            className="w-5 h-5 rounded-full bg-[rgba(94,106,210,0.3)] flex items-center justify-center text-[8px] text-[#5E6AD2] border border-[#16161C]"
                          >
                            {String.fromCharCode(65 + i)}
                          </div>
                        ))}
                      </div>
                      <span className="text-xs text-[#5E5E6B]">{agents} agents</span>
                    </div>
                    <span className="font-mono text-sm text-muted-foreground">
                      <CostDisplay cost={run.total_cost_usd || 0} />
                    </span>
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export function Component() {
  const navigate = useNavigate();
  const { data: providersData, isLoading: providersLoading } = useProviders();
  const { data: workflowsData, isLoading: workflowsLoading } = useWorkflows();
  const { data: appSettings, isLoading: settingsLoading } = useAppSettings();
  const [showNewWorkflowModal, setShowNewWorkflowModal] = useState(false);

  const hasProviders = (providersData?.total ?? 0) > 0;
  const workflowCount = workflowsData?.total ?? 0;
  const hasWorkflows = workflowCount > 0;
  const onboardingCompleted = appSettings?.onboarding_completed === true;
  const isLoading = providersLoading || workflowsLoading || settingsLoading;

  useEffect(() => {
    if (isLoading) return;
    if (!hasProviders && !onboardingCompleted) {
      navigate("/landing", { replace: true });
    }
  }, [isLoading, hasProviders, onboardingCompleted, navigate]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (!hasProviders && !onboardingCompleted) {
    return null;
  }

  if (hasWorkflows) {
    return (
      <div className="flex-1 flex flex-col">
        {/* Header Bar */}
        <header className="h-12 bg-[#16161C] border-b border-[#2D2D35] flex items-center justify-between px-4 z-40">
          <div className="flex items-center gap-3">
            <h1 className="text-base font-medium tracking-tight text-foreground">Dashboard</h1>
          </div>
          <div className="flex items-center gap-3">
            <Button
              className="h-9 px-4 bg-[#5E6AD2] hover:bg-[#717EE3] text-white"
              onClick={() => setShowNewWorkflowModal(true)}
            >
              <Plus className="w-4 h-4 mr-2" />
              New Workflow
            </Button>
          </div>
        </header>

        <PopulatedDashboard onNewWorkflow={() => setShowNewWorkflowModal(true)} />

        <NewWorkflowModal
          open={showNewWorkflowModal}
          onClose={() => setShowNewWorkflowModal(false)}
        />
      </div>
    );
  }

  return (
    <div className="flex-1 flex items-center justify-center p-8 bg-background">
      <div className="text-center max-w-[480px]">
        <div className="w-20 h-20 mx-auto mb-6 flex items-center justify-center bg-[#16161C] border border-[#2D2D35] rounded-lg text-primary">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="w-10 h-10"
          >
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="M3 9h18M9 21V9" />
            <circle cx="15" cy="15" r="2" />
            <line x1="16.5" y1="16.5" x2="19" y2="19" />
          </svg>
        </div>
        <h2 className="text-2xl font-semibold tracking-[-0.02em] mb-3">
          Create your first workflow
        </h2>
        <p className="text-[14px] text-[#9292A0] leading-[1.6] mb-8">
          Workflows are visual orchestrations of AI agents. Start from scratch with AI assistance,
          use a template, or import an existing YAML file.
        </p>

        <div className="grid grid-cols-3 gap-4 mb-8">
          <div
            className="flex flex-col items-center gap-3 py-6 px-4 rounded-lg border border-[#2D2D35] bg-[#16161C] opacity-50 cursor-not-allowed relative"
          >
            <div className="w-12 h-12 flex items-center justify-center bg-[#0D0D12] rounded-md text-primary/50">
              <Zap className="size-6" strokeWidth={1.5} />
            </div>
            <span className="text-[14px] font-medium text-foreground/50">Generate with AI</span>
            <span className="text-[12px] text-[#5E5E6B] leading-snug">
              Describe your workflow and let AI build it
            </span>
            <span className="text-[10px] font-semibold tracking-[0.08em] uppercase text-primary/60 mt-1">Coming soon</span>
          </div>

          <button
            onClick={() => setShowNewWorkflowModal(true)}
            className="flex flex-col items-center gap-3 py-6 px-4 rounded-lg bg-[#16161C] border border-[#2D2D35] hover:border-[#3F3F4A] hover:bg-[#22222A] transition-all group cursor-pointer"
          >
            <div className="w-12 h-12 flex items-center justify-center bg-[#0D0D12] rounded-md text-primary">
              <Plus className="size-6" strokeWidth={1.5} />
            </div>
            <span className="text-[14px] font-medium text-foreground">New Workflow</span>
            <span className="text-[12px] text-[#5E5E6B] leading-snug">
              Create a blank workflow from scratch
            </span>
          </button>

          <div
            className="flex flex-col items-center gap-3 py-6 px-4 rounded-lg bg-[#16161C] border border-[#2D2D35] opacity-50 cursor-not-allowed relative"
          >
            <div className="w-12 h-12 flex items-center justify-center bg-[#0D0D12] rounded-md text-primary/50">
              <Upload className="size-6" strokeWidth={1.5} />
            </div>
            <span className="text-[14px] font-medium text-foreground/50">Import YAML</span>
            <span className="text-[12px] text-[#5E5E6B] leading-snug">
              Upload an existing workflow file
            </span>
            <span className="text-[10px] font-semibold tracking-[0.08em] uppercase text-primary/60 mt-1">Coming soon</span>
          </div>
        </div>

        <p className="text-[13px] text-[#9292A0]">
          Need help?{" "}
          <a href="#" className="text-primary no-underline hover:underline">
            View documentation
          </a>{" "}
          or{" "}
          <a href="#" className="text-primary no-underline hover:underline">
            watch a tutorial
          </a>
        </p>
      </div>

      <NewWorkflowModal
        open={showNewWorkflowModal}
        onClose={() => setShowNewWorkflowModal(false)}
      />
    </div>
  );
}
