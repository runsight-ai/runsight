import { useRef, useEffect, useCallback } from "react";
import { parse } from "yaml";

export interface ValidationState {
  isValid: boolean;
  errorCount: number;
  errors: ValidationError[];
}

export interface ValidationError {
  message: string;
  line: number;
}

/**
 * Hook that validates YAML content with a 500ms debounce.
 * Sets Monaco markers on syntax errors and reports validation state.
 */
export function useYamlValidation(
  onValidation?: (state: ValidationState) => void,
) {
  const editorRef = useRef<unknown>(null);
  const monacoRef = useRef<unknown>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, []);

  const setEditorRefs = useCallback(
    (editor: unknown, monaco: unknown) => {
      editorRef.current = editor;
      monacoRef.current = monaco;
    },
    [],
  );

  const validate = useCallback(
    (value: string) => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }

      timerRef.current = setTimeout(() => {
        const monaco = monacoRef.current as {
          editor: {
            setModelMarkers: (
              model: unknown,
              owner: string,
              markers: unknown[],
            ) => void;
          };
          MarkerSeverity: { Error: number };
        } | null;

        const editor = editorRef.current as {
          getModel: () => unknown;
        } | null;

        if (!monaco || !editor) return;

        const model = editor.getModel();

        try {
          parse(value);
          // Valid YAML — clear markers
          monaco.editor.setModelMarkers(model, "yaml-validation", []);
          onValidation?.({ isValid: true, errorCount: 0, errors: [] });
        } catch (err: unknown) {
          const error = err as { message: string; linePos?: Array<{ line: number; col: number }> };
          const startLineNumber = error.linePos?.[0]?.line ?? 1;
          const startColumn = error.linePos?.[0]?.col ?? 1;

          const marker = {
            severity: monaco.MarkerSeverity.Error,
            message: error.message,
            startLineNumber,
            startColumn,
            endLineNumber: startLineNumber,
            endColumn: startColumn + 1,
          };

          monaco.editor.setModelMarkers(model, "yaml-validation", [marker]);
          onValidation?.({
            isValid: false,
            errorCount: 1,
            errors: [{ message: error.message, line: startLineNumber }],
          });
        }
      }, 500);
    },
    [onValidation],
  );

  return { validate, setEditorRefs };
}
