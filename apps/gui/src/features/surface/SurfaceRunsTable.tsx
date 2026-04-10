import {
  RUN_TABLE_CLASS,
  RUN_TABLE_CONTAINER_CLASS,
  RUN_TABLE_HEAD_CLASS,
  RUN_TABLE_HEADER_ROW_CLASS,
  RUN_TABLE_STATUS_HEAD_CLASS,
} from "@runsight/ui/runTable.styles";
import { Table, TableBody, TableHead, TableHeader, TableRow } from "@runsight/ui/table";
import { cn } from "@runsight/ui/utils";
import type { RunResponse } from "@runsight/shared/zod";

import { SurfaceRunRow } from "./SurfaceRunRow";

type SurfaceRunsTableProps = {
  runs: RunResponse[];
  currentRunId?: string;
  onRowClick: (runId: string) => void;
};

export function SurfaceRunsTable({
  runs,
  currentRunId,
  onRowClick,
}: SurfaceRunsTableProps) {
  if (runs.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted">
        No runs found for this workflow.
      </div>
    );
  }

  return (
    <div className={RUN_TABLE_CONTAINER_CLASS}>
      <Table className={RUN_TABLE_CLASS}>
        <TableHeader>
          <TableRow className={RUN_TABLE_HEADER_ROW_CLASS}>
            <TableHead className={cn(RUN_TABLE_HEAD_CLASS, RUN_TABLE_STATUS_HEAD_CLASS)}>
              <span className="sr-only">Status</span>
            </TableHead>
            <TableHead className={RUN_TABLE_HEAD_CLASS}>Run</TableHead>
            <TableHead className={RUN_TABLE_HEAD_CLASS}>Source</TableHead>
            <TableHead className={RUN_TABLE_HEAD_CLASS}>Started</TableHead>
            <TableHead className={RUN_TABLE_HEAD_CLASS}>Duration</TableHead>
            <TableHead className={RUN_TABLE_HEAD_CLASS}>Cost</TableHead>
            <TableHead className={RUN_TABLE_HEAD_CLASS}>Eval</TableHead>
            <TableHead className={RUN_TABLE_HEAD_CLASS}>Regr</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {runs.map((run) => (
            <SurfaceRunRow
              key={run.id}
              run={run}
              currentRunId={currentRunId}
              onSelect={onRowClick}
            />
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
