import { useState, useCallback } from "react";
import { useParams } from "react-router";
import { CanvasTopbar } from "./CanvasTopbar";
import { YamlEditor } from "./YamlEditor";

export function Component() {
  const { id } = useParams<{ id: string }>();
  const [isDirty, setIsDirty] = useState(false);

  const handleDirtyChange = useCallback((dirty: boolean) => {
    setIsDirty(dirty);
  }, []);

  return (
    <div className="flex flex-col h-full">
      <CanvasTopbar workflowId={id!} isDirty={isDirty} />
      <div className="flex-1 overflow-hidden">
        <YamlEditor workflowId={id!} onDirtyChange={handleDirtyChange} />
      </div>
    </div>
  );
}
