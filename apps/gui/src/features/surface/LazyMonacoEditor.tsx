import { lazy, Suspense } from "react";

const MonacoEditor = lazy(() => import("@monaco-editor/react"));

export function LazyMonacoEditor(props: Record<string, unknown>) {
  return (
    <Suspense fallback={<div>Loading editor...</div>}>
      <MonacoEditor {...props} />
    </Suspense>
  );
}
