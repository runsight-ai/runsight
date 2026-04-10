import { useState, useEffect, useRef } from "react";
import { useWorkflow } from "@/queries/workflows";
import { LazyMonacoEditor } from "./LazyMonacoEditor";
import { defineYamlTheme } from "./yamlTheme";
import { useYamlValidation, type ValidationState } from "./useYamlValidation";
import { useCanvasStore } from "@/store/canvas";

interface YamlEditorProps {
  workflowId?: string;
  yaml?: string;
  readOnly?: boolean;
  onDirtyChange?: (dirty: boolean) => void;
  onValidation?: (state: ValidationState) => void;
}

export function YamlEditor({ workflowId, yaml: yamlProp, readOnly = false, onDirtyChange, onValidation }: YamlEditorProps) {
  const { data: workflow } = useWorkflow(workflowId ?? "");
  const resolvedYaml = yamlProp ?? workflow?.yaml ?? "";
  const [editorYaml, setEditorYaml] = useState(resolvedYaml);
  const [isDirty, setIsDirty] = useState(false);
  const contentRef = useRef(resolvedYaml);
  const { validate, setEditorRefs } = useYamlValidation(onValidation);

  useEffect(() => {
    setEditorYaml(resolvedYaml);
    contentRef.current = resolvedYaml;
    setIsDirty(false);

    if (yamlProp != null) {
      useCanvasStore.getState().setYamlContent(yamlProp);
      useCanvasStore.getState().markSaved();
      return;
    }
    if (workflow?.yaml != null) {
      useCanvasStore.getState().setYamlContent(workflow.yaml);
      useCanvasStore.getState().markSaved();
    }
  }, [resolvedYaml, yamlProp, workflow?.yaml]);

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
    const nextValue = value ?? "";
    contentRef.current = nextValue;
    setEditorYaml(nextValue);
    setIsDirty(true);
    validate(contentRef.current);
    useCanvasStore.getState().setYamlContent(contentRef.current);
  }

  return (
    <div data-testid="workflow-yaml-editor" className="flex-1 h-full">
      <LazyMonacoEditor
        language="yaml"
        theme="runsight-yaml"
        value={editorYaml}
        height="100%"
        onChange={onChange}
        onMount={onMount}
        beforeMount={handleEditorMount}
        options={{ readOnly }}
      />
    </div>
  );
}
