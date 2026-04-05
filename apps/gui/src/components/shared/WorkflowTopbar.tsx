import type { ReactNode } from "react";
import { Link, useInRouterContext } from "react-router";

import { Button } from "@runsight/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@runsight/ui/tabs";

interface WorkflowTopbarProps {
  backTo: string;
  backLabel: string;
  title: ReactNode;
  titleAfter?: ReactNode;
  metrics?: ReactNode;
  actions?: ReactNode;
  activeTab: string;
  onValueChange: (value: string) => void;
  toggleVisibility?: { canvas: boolean; yaml: boolean };
}

export function WorkflowTopbar({
  backTo,
  backLabel,
  title,
  titleAfter,
  metrics,
  actions,
  activeTab,
  onValueChange,
  toggleVisibility,
}: WorkflowTopbarProps) {
  const hasRouter = useInRouterContext();

  const backButton = (
    <Button variant="ghost" size="icon-sm" className="w-8 h-8" aria-label={backLabel}>
      <span aria-hidden="true" className="text-base leading-none">
        ‹
      </span>
    </Button>
  );

  return (
    <header
      className="flex items-center h-[var(--header-height)] border-b border-border-subtle px-4"
      style={{ gridColumn: "1 / -1", gridRow: "1" }}
    >
      <div className="flex items-center gap-2 flex-1 min-w-0">
        {hasRouter ? <Link to={backTo}>{backButton}</Link> : <a href={backTo}>{backButton}</a>}
        <div className="flex min-w-0 items-center gap-2">
          {title}
          {titleAfter}
        </div>
      </div>

      <div className="flex items-center gap-3">
        {metrics}
        {toggleVisibility && (toggleVisibility.canvas || toggleVisibility.yaml) ? (
          <Tabs value={activeTab} onValueChange={onValueChange}>
            <TabsList variant="contained">
              {toggleVisibility.canvas ? (
                <TabsTrigger value="canvas" data-testid="workflow-tab-canvas">
                  Canvas
                </TabsTrigger>
              ) : null}
              {toggleVisibility.yaml ? (
                <TabsTrigger value="yaml" data-testid="workflow-tab-yaml">
                  YAML
                </TabsTrigger>
              ) : null}
            </TabsList>
          </Tabs>
        ) : null}
      </div>

      <div className="flex items-center gap-2 flex-1 justify-end">{actions}</div>
    </header>
  );
}
