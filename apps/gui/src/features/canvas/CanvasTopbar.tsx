import { useState, useEffect, useRef } from "react";
import { useWorkflow, useUpdateWorkflow } from "@/queries/workflows";
import { Tabs, TabsList, TabsTrigger } from "@runsight/ui/tabs";
import { Button } from "@runsight/ui/button";
import { RunButton } from "./RunButton";
import { ExecutionMetrics } from "./ExecutionMetrics";
import { useCanvasStore } from "@/store/canvas";
import { useRun } from "@/queries/runs";
import { Save } from "lucide-react";

interface CanvasTopbarProps {
  workflowId: string;
  activeTab: string;
  onValueChange: (value: string) => void;
  isDirty?: boolean;
  onSave?: () => void;
  yamlValid?: boolean;
  errorCount?: number;
  onAddApiKey?: () => void;
}

export function CanvasTopbar({ workflowId, activeTab, onValueChange, isDirty, onSave, yamlValid: _yamlValid = true, errorCount: _errorCount = 0, onAddApiKey }: CanvasTopbarProps) {
  const { data: workflow } = useWorkflow(workflowId);
  const updateWorkflow = useUpdateWorkflow();

  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState("");

  // Track last completed/failed run for metrics display
  const activeRunId = useCanvasStore((s) => s.activeRunId);
  const [lastTerminalRunId, setLastTerminalRunId] = useState<string | null>(null);
  const prevActiveRunId = useRef<string | null>(null);

  const { data: trackedRun } = useRun(prevActiveRunId.current ?? "", {
    refetchInterval: prevActiveRunId.current ? 2000 : false,
  });

  // When activeRunId is set, remember it for post-completion tracking
  useEffect(() => {
    if (activeRunId) {
      prevActiveRunId.current = activeRunId;
    }
  }, [activeRunId]);

  // When tracked run reaches terminal state, surface it for metrics
  useEffect(() => {
    const status = trackedRun?.status;
    if (prevActiveRunId.current && (status === "completed" || status === "failed")) {
      setLastTerminalRunId(prevActiveRunId.current);
    }
  }, [trackedRun?.status]);

  const workflowName = workflow?.name ?? "Untitled Workflow";

  function startEditing() {
    setEditName(workflowName);
    setIsEditing(true);
  }

  function saveName() {
    setIsEditing(false);
    const trimmed = editName.trim();
    if (trimmed && trimmed !== workflowName) {
      updateWorkflow.mutate({ id: workflowId, data: { name: trimmed } });
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      saveName();
    }
  }

  return (
    <header
      className="flex items-center h-[var(--header-height)] border-b border-border-subtle px-4"
      style={{ gridColumn: "1 / -1", gridRow: "1" }}
    >
      {/* Left: Workflow name */}
      <div className="flex items-center gap-2 flex-1 min-w-0">
        {isEditing ? (
          <input
            className="font-sans text-lg font-medium text-heading bg-transparent border border-transparent rounded-sm px-1 py-[2px] outline-none hover:bg-surface-hover focus:border-border-focus"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            onBlur={saveName}
            onKeyDown={handleKeyDown}
            autoFocus
          />
        ) : (
          <span
            className="text-lg font-medium text-heading cursor-pointer border border-transparent rounded-sm px-1 py-[2px] hover:bg-surface-hover"
            onClick={startEditing}
          >
            {workflowName}
          </span>
        )}
      </div>

      {/* Center: Canvas | YAML toggle */}
      <div className="flex items-center">
        <Tabs value={activeTab} onValueChange={onValueChange}>
          <TabsList variant="contained">
            <TabsTrigger value="canvas" className="opacity-50">
              Canvas
            </TabsTrigger>
            <TabsTrigger value="yaml">YAML</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Right: actions */}
      <div className="flex items-center gap-2 flex-1 justify-end">
        {isDirty && <span className="h-2 w-2 rounded-full bg-interactive-default" aria-label="unsaved indicator" />}
        <Button
          variant={isDirty ? "primary" : "ghost"}
          size="sm"
          onClick={onSave}
        >
          <Save className="w-4 h-4" />
          Save
        </Button>
        <ExecutionMetrics runId={lastTerminalRunId} />
        <RunButton workflowId={workflowId} onAddApiKey={onAddApiKey} />
      </div>
    </header>
  );
}