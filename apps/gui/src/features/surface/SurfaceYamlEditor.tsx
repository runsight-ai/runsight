import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { useWorkflow } from "@/queries/workflows";
import { defineYamlTheme } from "./yamlTheme";
import { useYamlValidation, type ValidationState } from "./useYamlValidation";
import { useCanvasStore } from "@/store/canvas";

const MonacoEditor = lazy(() => import("@monaco-editor/react"));

interface SurfaceYamlEditorProps {
  workflowId?: string;
  yaml?: string;
  readOnly?: boolean;
  onDirtyChange?: (dirty: boolean) => void;
  onValidation?: (state: ValidationState) => void;
}

export function SurfaceYamlEditor({
  workflowId,
  yaml: yamlProp,
  readOnly = false,
  onDirtyChange,
  onValidation,
}: SurfaceYamlEditorProps) {
  const { data: workflow } = useWorkflow(workflowId ?? "");
  const resolvedYaml = yamlProp ?? workflow?.yaml ?? "";
  const [editorYaml, setEditorYaml] = useState(resolvedYaml);
  const [isDirty, setIsDirty] = useState(false);
  const contentRef = useRef(resolvedYaml);
  const { validate, setEditorRefs } = useYamlValidation(onValidation);

  useEffect(() => {
    const canvasState = useCanvasStore.getState() as {
      setYamlContent: (yaml: string) => void;
      markSaved?: () => void;
    };

    setEditorYaml(resolvedYaml);
    contentRef.current = resolvedYaml;
    setIsDirty(false);

    if (yamlProp != null) {
      canvasState.setYamlContent(yamlProp);
      canvasState.markSaved?.();
      return;
    }
    if (workflow?.yaml != null) {
      canvasState.setYamlContent(workflow.yaml);
      canvasState.markSaved?.();
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
      <Suspense fallback={<div>Loading editor...</div>}>
        <MonacoEditor
          language="yaml"
          theme="runsight-yaml"
          value={editorYaml}
          height="100%"
          onChange={onChange}
          onMount={onMount}
          beforeMount={handleEditorMount}
          options={{ readOnly }}
        />
      </Suspense>
    </div>
  );
}
