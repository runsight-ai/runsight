import { useState, useEffect } from "react";
import { gitApi } from "../../api/git";

export function useOverlayYaml(
  workflowId: string,
  overlayRef: string | null,
): { overlayYaml: string | null; isOverlayLoading: boolean } {
  const [overlayYaml, setOverlayYaml] = useState<string | null>(null);
  const [isOverlayLoading, setIsOverlayLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    if (!workflowId || !overlayRef) {
      setOverlayYaml(null);
      setIsOverlayLoading(false);
      return () => {
        cancelled = true;
      };
    }

    setOverlayYaml(null);
    setIsOverlayLoading(true);
    gitApi
      .getGitFile(overlayRef, `custom/workflows/${workflowId}.yaml`)
      .then(({ content }) => {
        if (cancelled) return;
        setOverlayYaml(content);
      })
      .catch(() => {
        if (cancelled) return;
        setOverlayYaml(null);
      })
      .finally(() => {
        if (cancelled) return;
        setIsOverlayLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [overlayRef, workflowId]);

  return { overlayYaml, isOverlayLoading };
}
