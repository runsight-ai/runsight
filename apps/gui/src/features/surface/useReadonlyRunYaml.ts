import { useState, useEffect } from "react";
import { gitApi } from "../../api/git";
import type { WorkflowSurfaceMode } from "./surfaceContract";

type Run = {
  workflow_id?: string;
  commit_sha?: string | null;
};

export function useReadonlyRunYaml(
  mode: WorkflowSurfaceMode,
  run: Run | null | undefined,
): { readonlyYaml: string | null; isReadonlyYamlLoading: boolean } {
  const [readonlyYaml, setReadonlyYaml] = useState<string | null>(null);
  const [isReadonlyYamlLoading, setIsReadonlyYamlLoading] = useState(false);

  useEffect(() => {
    if (mode !== "readonly" || !run?.workflow_id || !run?.commit_sha) {
      setReadonlyYaml(null);
      setIsReadonlyYamlLoading(false);
      return;
    }

    let cancelled = false;
    setReadonlyYaml(null);
    setIsReadonlyYamlLoading(true);
    gitApi
      .getGitFile(run.commit_sha, `custom/workflows/${run.workflow_id}.yaml`)
      .then(({ content }) => {
        if (cancelled) return;
        setReadonlyYaml(content);
      })
      .catch(() => {
        if (cancelled) return;
        setReadonlyYaml(null);
      })
      .finally(() => {
        if (cancelled) return;
        setIsReadonlyYamlLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [mode, run?.commit_sha, run?.workflow_id]);

  return { readonlyYaml, isReadonlyYamlLoading };
}
