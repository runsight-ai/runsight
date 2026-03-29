import { useState } from "react";
import { useParams } from "react-router";
import { Layout } from "lucide-react";
import { CanvasTopbar } from "./CanvasTopbar";
import { EmptyState } from "@/components/shared/EmptyState";

export function Component() {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState("yaml");

  return (
    <div className="flex flex-col h-full">
      <CanvasTopbar
        workflowId={id!}
        activeTab={activeTab}
        onValueChange={setActiveTab}
      />
      {activeTab === "canvas" ? (
        <EmptyState
          icon={Layout}
          title="Visual canvas coming soon"
          description="Switch to YAML to edit your workflow."
          action={{ label: "Switch to YAML", onClick: () => setActiveTab("yaml") }}
        />
      ) : (
        <div className="flex-1" />
      )}
    </div>
  );
}
