import { useNavigate } from "react-router";
import { Card } from "@runsight/ui/card";
import { StatusDot } from "@runsight/ui/status-dot";
import { Skeleton } from "@runsight/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@runsight/ui/table";
import type { RunResponse } from "@runsight/shared/zod";
import { formatElapsed, formatCost, formatRunStatus, formatRunNumber } from "../utils";

interface ActiveRunsTableProps {
  runs: RunResponse[];
  isLoading: boolean;
}

export function ActiveRunsTable({ runs, isLoading }: ActiveRunsTableProps) {
  const navigate = useNavigate();
  const visible = runs.slice(0, 5);

  return (
    <section className="space-y-3">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-heading">
          <span className="sr-only font-mono text-xs uppercase tracking-wider text-muted">ACTIVE RUNS</span>
          Active Runs
        </h2>
        {runs.length > 5 && (
          <button className="text-sm font-medium text-interactive-default hover:text-accent-11" onClick={() => navigate("/runs?status=active")}>see all →</button>
        )}
      </div>
      <Card className="overflow-hidden">
        <Table className="table-fixed">
          <colgroup>
            <col style={{ width: "40px" }} /><col style={{ width: "42%" }} /><col style={{ width: "16%" }} /><col style={{ width: "20%" }} /><col style={{ width: "22%" }} />
          </colgroup>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-10"><span className="sr-only">Status</span></TableHead>
              <TableHead>Workflow</TableHead>
              <TableHead>Run</TableHead>
              <TableHead className="text-right">Elapsed</TableHead>
              <TableHead className="text-right">Cost</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <><TableRow className="hover:bg-transparent"><TableCell colSpan={5} className="py-3"><Skeleton className="h-10 w-full" /></TableCell></TableRow>
              <TableRow className="hover:bg-transparent"><TableCell colSpan={5} className="py-3"><Skeleton className="h-10 w-full" /></TableCell></TableRow></>
            ) : (
              visible.map((run) => (
                <TableRow key={run.id} className="cursor-pointer bg-surface-primary hover:bg-surface-primary" onClick={() => navigate(`/runs/${run.id}`)}>
                  <TableCell className="align-middle">
                    <div className="flex items-center justify-center">
                      <StatusDot variant={run.status === "running" ? "active" : "neutral"} animate={run.status === "running" ? "pulse" : "none"} title={formatRunStatus(run.status)} />
                      <span className="sr-only">{formatRunStatus(run.status)}</span>
                    </div>
                  </TableCell>
                  <TableCell><span className="font-medium text-heading">{run.workflow_name}</span></TableCell>
                  <TableCell data-type="id" className="text-muted">{formatRunNumber(run.run_number, run.id)}</TableCell>
                  <TableCell data-type="metric" className="text-right text-muted">{formatElapsed(run.started_at)}</TableCell>
                  <TableCell data-type="metric" className={run.status === "running" ? "text-right text-success-11" : "text-right text-muted"}>{formatCost(run.total_cost_usd)}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>
    </section>
  );
}
