import type { ReactNode } from "react";

type SurfaceShellProps = {
  topbar: ReactNode;
  center: ReactNode;
  bottomPanel: ReactNode;
  statusBar: ReactNode;
};

export function SurfaceShell({
  topbar,
  center,
  bottomPanel,
  statusBar,
}: SurfaceShellProps) {
  return (
    <div
      className="grid h-full"
      style={{
        gridTemplateRows: "var(--header-height) 1fr auto var(--status-bar-height)",
        gridTemplateColumns: "1fr",
      }}
    >
      <div data-testid="surface-topbar" style={{ gridColumn: "1 / -1", gridRow: "1" }}>
        {topbar}
      </div>
      <div
        data-testid="surface-center"
        className="relative flex flex-col overflow-hidden"
        style={{ gridColumn: "1", gridRow: "2" }}
      >
        {center}
      </div>
      <div
        data-testid="surface-bottom-panel"
        style={{ gridColumn: "1 / -1", gridRow: "3" }}
      >
        {bottomPanel}
      </div>
      <div
        data-testid="surface-status-bar"
        style={{ gridColumn: "1 / -1", gridRow: "4" }}
      >
        {statusBar}
      </div>
    </div>
  );
}
