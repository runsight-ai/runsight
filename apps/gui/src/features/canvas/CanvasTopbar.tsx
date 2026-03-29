import { useState } from "react";
import { useWorkflow, useUpdateWorkflow } from "@/queries/workflows";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface CanvasTopbarProps {
  workflowId: string;
  activeTab: string;
  onValueChange: (value: string) => void;
}

export function CanvasTopbar({ workflowId, activeTab, onValueChange }: CanvasTopbarProps) {
  const { data: workflow } = useWorkflow(workflowId);
  const updateWorkflow = useUpdateWorkflow();

  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState("");

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
    <header className="flex items-center h-[var(--header-height)] border-b border-border-default px-4">
      {/* Left: Logo + Workflow name */}
      <div className="flex items-center gap-2">
        <WorkflowLogo />
        {isEditing ? (
          <input
            className="bg-transparent text-sm font-medium text-heading outline-none border-b border-border-default"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            onBlur={saveName}
            onKeyDown={handleKeyDown}
            autoFocus
          />
        ) : (
          <span
            className="text-sm font-medium text-heading cursor-pointer"
            onClick={startEditing}
          >
            {workflowName}
          </span>
        )}
      </div>

      {/* Center: Canvas | YAML toggle */}
      <div className="flex-1 flex justify-center">
        <Tabs value={activeTab} onValueChange={onValueChange}>
          <TabsList variant="contained">
            <TabsTrigger value="canvas" className="opacity-50">
              Canvas
            </TabsTrigger>
            <TabsTrigger value="yaml">YAML</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Right: actions placeholder */}
      <div className="flex items-center gap-2 ml-auto">
        <span className="text-sm text-secondary">Save</span>
        <span className="text-sm text-secondary">Run</span>
      </div>
    </header>
  );
}

function WorkflowLogo() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 20 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        d="M3 5h14M3 10h14M3 15h14"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
