import { useState, useCallback, useEffect, useRef } from "react";
import { useParams, useBlocker } from "react-router";
import { Layout } from "lucide-react";
import { CanvasTopbar } from "./CanvasTopbar";
import { CanvasStatusBar } from "./CanvasStatusBar";
import { PaletteSidebar } from "./PaletteSidebar";
import { EmptyState } from "@/components/shared/EmptyState";
import { YamlEditor } from "./YamlEditor";
import { useUpdateWorkflow } from "@/queries/workflows";
import { Dialog, DialogContent, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export function Component() {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState("yaml");
  const [isDirty, setIsDirty] = useState(false);
  const yamlRef = useRef("");
  const updateWorkflow = useUpdateWorkflow();

  const blocker = useBlocker(isDirty);

  const handleDirtyChange = useCallback((dirty: boolean) => {
    setIsDirty(dirty);
  }, []);

  const handleSave = useCallback(() => {
    updateWorkflow.mutate(
      { id: id!, data: { yaml: yamlRef.current } },
      { onSuccess: () => setIsDirty(false) },
    );
  }, [id, updateWorkflow]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        handleSave();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleSave]);

  return (
    <div className="flex flex-col h-full">
      <CanvasTopbar
        workflowId={id!}
        activeTab={activeTab}
        onValueChange={setActiveTab}
        isDirty={isDirty}
        onSave={handleSave}
      />
      <div className="flex flex-row flex-1 overflow-hidden h-full">
        <PaletteSidebar />
        {activeTab === "canvas" ? (
          <EmptyState
            icon={Layout}
            title="Visual canvas coming soon"
            description="Switch to YAML to edit your workflow."
            action={{ label: "Switch to YAML", onClick: () => setActiveTab("yaml") }}
          />
        ) : (
          <div className="flex-1 overflow-hidden">
            <YamlEditor workflowId={id!} onDirtyChange={handleDirtyChange} />
          </div>
        )}
      </div>

      <CanvasStatusBar activeTab={activeTab} />

      {/* Unsaved changes dialog */}
      <Dialog open={blocker.state === "blocked"}>
        <DialogContent>
          <DialogTitle>You have unsaved changes</DialogTitle>
          <p className="text-sm text-secondary px-5 py-4">
            Your changes will be lost if you leave without saving.
          </p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => blocker.reset?.()}>
              Cancel
            </Button>
            <Button variant="secondary" onClick={() => blocker.proceed?.()}>
              Discard
            </Button>
            <Button
              variant="primary"
              onClick={() => {
                handleSave();
                blocker.proceed?.();
              }}
            >
              Save & Leave
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
