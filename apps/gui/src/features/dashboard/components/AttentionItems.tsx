import { useNavigate } from "react-router";
import { AlertTriangle, Activity } from "lucide-react";
import { Card } from "@runsight/ui/card";
import { Badge } from "@runsight/ui/badge";
import type { AttentionItem } from "@runsight/shared/zod";
import type { RunResponse } from "@runsight/shared/zod";
import {
  formatAttentionType,
  formatAttentionTitle,
  formatAttentionDescription,
} from "../utils";

interface AttentionItemsProps {
  items: AttentionItem[];
  recentRunsById: Map<string, RunResponse>;
}

export function AttentionItems({ items, recentRunsById }: AttentionItemsProps) {
  const navigate = useNavigate();
  const visible = items.slice(0, 3);

  return (
    <section aria-label="Items needing attention" className="space-y-3">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-heading">
          <span className="sr-only font-mono text-xs uppercase tracking-wider text-muted">ATTENTION</span>
          Attention
        </h2>
        {items.length > 3 && (
          <button className="text-sm font-medium text-interactive-default hover:text-accent-11" onClick={() => navigate("/runs?attention=only")}>see all →</button>
        )}
      </div>
      <div className="space-y-2">
        {visible.map((item) => {
          const isInfo = item.type === "new_baseline";
          const runInfo = recentRunsById.get(item.run_id);
          return (
            <Card key={`${item.run_id}-${item.type}`} interactive className="rounded-md bg-surface-tertiary px-3 py-3" onClick={() => navigate(`/runs/${item.run_id}`)}>
              <div className="flex items-start gap-3">
                <div className={isInfo ? "flex size-8 shrink-0 items-center justify-center rounded-full bg-info-3 text-info-11" : "flex size-8 shrink-0 items-center justify-center rounded-full bg-warning-3 text-warning-11"}>
                  {isInfo ? <Activity className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium leading-5 text-heading">{formatAttentionTitle(item.title, runInfo)}</p>
                      <p className="mt-0.5 line-clamp-2 text-2xs leading-5 text-muted">{formatAttentionDescription(item.title, item.description)}</p>
                    </div>
                    <Badge variant={isInfo ? "info" : "warning"} className="w-fit shrink-0">{formatAttentionType(item.type)}</Badge>
                  </div>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </section>
  );
}
