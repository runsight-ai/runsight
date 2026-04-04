import { useState, useEffect, useRef } from "react";
import { useWorkflow } from "@/queries/workflows";
import { LazyMonacoEditor } from "./LazyMonacoEditor";
import { defineYamlTheme } from "./yamlTheme";
import { useYamlValidation, type ValidationState } from "./useYamlValidation";
import { useCanvasStore } from "@/store/canvas";

interface YamlEditorProps {
  workflowId: string;
  readOnly?: boolean;
  onDirtyChange?: (dirty: boolean) => void;
  onValidation?: (state: ValidationState) => void;
}

export function YamlEditor({ workflowId, readOnly = false, onDirtyChange, onValidation }: YamlEditorProps) {
  const { data: workflow } = useWorkflow(workflowId);
  const [isDirty, setIsDirty] = useState(false);
  const contentRef = useRef(workflow?.yaml ?? "");
  const { validate, setEditorRefs } = useYamlValidation(onValidation);

  useEffect(() => {
    if (workflow?.yaml != null) {
      contentRef.current = workflow.yaml;
      setIsDirty(false);
      useCanvasStore.getState().setYamlContent(workflow.yaml);
    }
  }, [workflow?.yaml]);

  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

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
    useCanvasStore.getState().setYamlContent(contentRef.current);
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
        options={{ readOnly }}
      />
    </div>
  );
}
