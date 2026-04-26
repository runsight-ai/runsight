import { useEffect } from "react";

import { useContextAuditStore } from "@/store/contextAudit";

type UseRunContextAuditHook = (
  runId: string,
  params?: { page_size?: number; node_id?: string },
) => {
  fetchNextPage: () => Promise<unknown>;
  hasNextPage?: boolean;
};

type UseRunContextAuditStreamHook = (
  runId: string | null | undefined,
) => void;

type UseSurfaceBottomPanelAuditParams = {
  runId: string | undefined;
  useRunContextAudit: UseRunContextAuditHook;
  useRunContextAuditStream: UseRunContextAuditStreamHook;
};

export function useSurfaceBottomPanelAudit({
  runId,
  useRunContextAudit,
  useRunContextAuditStream: _useRunContextAuditStream,
}: UseSurfaceBottomPanelAuditParams) {
  const replaceRunEvents = useContextAuditStore((state) => state.replaceRunEvents);
  const contextAuditQuery = useRunContextAudit(runId ?? "", { page_size: 100 });

  useEffect(() => {
    if (!runId) {
      return;
    }
    const currentEvents = useContextAuditStore.getState().eventsByRun[runId] ?? [];
    replaceRunEvents(runId, currentEvents);
  }, [replaceRunEvents, runId]);

  return contextAuditQuery;
}
