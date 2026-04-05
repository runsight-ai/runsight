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
      className="flex h-[var(--header-height)] items-center gap-3 border-b border-border-subtle px-4"
      style={{ gridColumn: "1 / -1", gridRow: "1" }}
    >
      <div className="topbar__left flex min-w-0 flex-1 items-center gap-2">
        {hasRouter ? <Link to={backTo}>{backButton}</Link> : <a href={backTo}>{backButton}</a>}
        <div className="flex min-w-0 items-center gap-2">
          {title}
          {titleAfter}
        </div>
      </div>

      <div className="topbar__metrics flex shrink-0 items-center gap-2">
        {metrics}
      </div>

      <div className="topbar__center flex shrink-0 items-center">
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

      <div className="topbar__actions flex shrink-0 items-center gap-2">{actions}</div>
    </header>
  );
}
