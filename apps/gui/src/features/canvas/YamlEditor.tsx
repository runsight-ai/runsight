import { useState, useEffect, useRef, useCallback } from "react";
import { useWorkflow, useUpdateWorkflow } from "@/queries/workflows";
import { LazyMonacoEditor } from "./LazyMonacoEditor";
import { defineYamlTheme } from "./yamlTheme";
import { useYamlValidation, type ValidationState } from "./useYamlValidation";

interface YamlEditorProps {
  workflowId: string;
  onDirtyChange?: (dirty: boolean) => void;
  onValidation?: (state: ValidationState) => void;
}

export function YamlEditor({ workflowId, onDirtyChange, onValidation }: YamlEditorProps) {
  const { data: workflow } = useWorkflow(workflowId);
  const updateWorkflow = useUpdateWorkflow();
  const [isDirty, setIsDirty] = useState(false);
  const contentRef = useRef(workflow?.yaml ?? "");
  const { validate, setEditorRefs } = useYamlValidation(onValidation);

  useEffect(() => {
    if (workflow?.yaml != null) {
      contentRef.current = workflow.yaml;
    }
  }, [workflow?.yaml]);

  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

  const handleSave = useCallback(() => {
    updateWorkflow.mutate(
      { id: workflowId, data: { yaml: contentRef.current } },
      { onSuccess: () => setIsDirty(false) },
    );
  }, [workflowId, updateWorkflow]);

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

  function handleEditorMount(monaco: unknown) {
    defineYamlTheme(monaco as Parameters<typeof defineYamlTheme>[0]);
  }

  function onMount(editor: unknown, monaco: unknown) {
    setEditorRefs(editor, monaco);
  }

  function onChange(value: string | undefined) {
    contentRef.current = value ?? "";
    setIsDirty(true);
    validate(contentRef.current);
  }

  return (
    <div className="flex-1 h-full">
      <LazyMonacoEditor
        language="yaml"
        theme="runsight-yaml"
        value={workflow?.yaml ?? ""}
        height="100%"
        onChange={onChange}
        onMount={onMount}
        beforeMount={handleEditorMount}
      />
    </div>
  );
}
