import { useEffect, useMemo, useState } from "react";
import type { RunResponse } from "@runsight/shared/zod";

import { useRuns } from "@/queries/runs";
import { useCanvasStore } from "@/store/canvas";

type UseSurfaceBottomPanelRunSelectionParams = {
  initialRunId?: string;
  workflowId?: string;
};

export function useSurfaceBottomPanelRunSelection({
  initialRunId,
  workflowId,
}: UseSurfaceBottomPanelRunSelectionParams) {
  const [selectedRunId, setSelectedRunId] = useState<string | undefined>(initialRunId);
  const activeRunId = useCanvasStore((state) => state.activeRunId);
  const { data: runsData } = useRuns(
    workflowId ? { workflow_id: workflowId } : undefined,
  );

  const sortedRuns = useMemo(() => {
    const items = runsData?.items ?? [];
    return [...items].sort((left, right) => {
      const leftTime = left.started_at ?? left.created_at ?? 0;
      const rightTime = right.started_at ?? right.created_at ?? 0;
      return rightTime - leftTime;
    });
  }, [runsData?.items]);

  useEffect(() => {
    setSelectedRunId(initialRunId);
  }, [initialRunId, workflowId]);

  const hasSelectedRun = useMemo(
    () => (selectedRunId ? sortedRuns.some((run) => run.id === selectedRunId) : false),
    [selectedRunId, sortedRuns],
  );

  useEffect(() => {
    const fallbackRunId = activeRunId ?? (hasSelectedRun ? selectedRunId : undefined) ?? initialRunId ?? sortedRuns[0]?.id;
    if (fallbackRunId !== selectedRunId) {
      setSelectedRunId(fallbackRunId);
    }
  }, [activeRunId, hasSelectedRun, initialRunId, selectedRunId, sortedRuns]);

  const currentRunId =
    activeRunId ?? (hasSelectedRun ? selectedRunId : undefined) ?? initialRunId ?? sortedRuns[0]?.id;

  const selectRun = (runId: string) => {
    setSelectedRunId(runId);
  };

  return {
    currentRunId,
    sortedRuns: sortedRuns as RunResponse[],
    selectRun,
  };
}
