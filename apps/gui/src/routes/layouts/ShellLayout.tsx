import { NavLink, Outlet } from "react-router";
import { RouteErrorBoundary } from "@/components/shared/ErrorBoundary";
import {
  LayoutDashboard,
  Workflow,
  Bot,
  Settings,
} from "lucide-react";
import { cn } from "@/utils/helpers";

const NAV_ITEMS = [
  { to: "/", icon: LayoutDashboard, label: "Home", end: true },
  { to: "/flows", icon: Workflow, label: "Flows" },
  { to: "/souls", icon: Bot, label: "Souls" },
] as const;

const BOTTOM_NAV = [
  { to: "/settings", icon: Settings, label: "Settings" },
] as const;

export function ShellLayout() {
  return (
    <div className="h-screen flex overflow-hidden bg-surface-primary text-primary">
      {/* Sidebar */}
      <aside
        style={{
          backgroundColor: "var(--sidebar-bg)",
          width: "var(--sidebar-width-expanded)",
        }}
        className="flex flex-col border-r border-border-subtle"
      >
        {/* Logo */}
        <div className="h-14 px-3 flex items-center gap-2 shrink-0">
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            className="shrink-0"
          >
            <circle cx="12" cy="5" r="2.5" fill="var(--interactive-default)" />
            <circle
              cx="5"
              cy="17"
              r="2.5"
              fill="var(--interactive-default)"
              opacity="0.7"
            />
            <circle
              cx="19"
              cy="17"
              r="2.5"
              fill="var(--interactive-default)"
              opacity="0.7"
            />
            <circle
              cx="12"
              cy="13"
              r="1.5"
              fill="var(--interactive-default)"
              opacity="0.5"
            />
            <line
              x1="12"
              y1="7.5"
              x2="12"
              y2="11.5"
              stroke="var(--interactive-default)"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
            <line
              x1="10.8"
              y1="14"
              x2="6.5"
              y2="15.5"
              stroke="var(--interactive-default)"
              strokeWidth="1.5"
              strokeLinecap="round"
              opacity="0.6"
            />
            <line
              x1="13.2"
              y1="14"
              x2="17.5"
              y2="15.5"
              stroke="var(--interactive-default)"
              strokeWidth="1.5"
              strokeLinecap="round"
              opacity="0.6"
            />
          </svg>
          <span
            className="text-lg font-bold tracking-tight text-primary"
            style={{ fontFamily: "'Geist', sans-serif" }}
          >
            Runsight
          </span>
        </div>

        {/* Main nav */}
        <nav className="flex-1 py-2 px-2 overflow-y-auto">
          {NAV_ITEMS.map(({ to, icon: Icon, label, ...rest }) => (
            <NavLink
              key={to}
              to={to}
              end={"end" in rest}
              className={({ isActive }) =>
                cn(
                  "relative flex items-center gap-2 px-2 rounded-md transition-colors",
                  "text-[length:var(--font-size-md)] font-normal",
                  "h-[var(--control-height-sm)]",
                  isActive
                    ? "bg-[var(--surface-selected)] text-[var(--text-heading)]"
                    : "text-[var(--sidebar-fg)] hover:bg-[var(--sidebar-hover)]",
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span
                      className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r-sm"
                      style={{ background: "var(--sidebar-active-indicator)" }}
                    />
                  )}
                  <Icon style={{ width: "var(--icon-size-md)", height: "var(--icon-size-md)" }} className="shrink-0" strokeWidth={1.5} />
                  <span>{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Bottom nav */}
        <div className="p-2">
          {BOTTOM_NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "relative flex items-center gap-2 px-2 rounded-md transition-colors",
                  "text-[length:var(--font-size-md)] font-normal",
                  "h-[var(--control-height-sm)]",
                  isActive
                    ? "bg-[var(--surface-selected)] text-[var(--text-heading)]"
                    : "text-[var(--sidebar-fg)] hover:bg-[var(--sidebar-hover)]",
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span
                      className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r-sm"
                      style={{ background: "var(--sidebar-active-indicator)" }}
                    />
                  )}
                  <Icon style={{ width: "var(--icon-size-md)", height: "var(--icon-size-md)" }} className="shrink-0" strokeWidth={1.5} />
                  <span>{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </div>
      </aside>

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Page content */}
        <main className="flex-1 flex flex-col overflow-y-auto">
          <RouteErrorBoundary>
            <Outlet />
          </RouteErrorBoundary>
        </main>

      </div>
    </div>
  );
}
