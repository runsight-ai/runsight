import { NavLink, Outlet, useLocation } from "react-router";
import { useProviders } from "@/queries/settings";
import { RouteErrorBoundary } from "@/components/shared/ErrorBoundary";
import {
  LayoutDashboard,
  Workflow,
  Bot,
  ListTodo,
  CheckSquare,
  Play,
  Settings,
  Search,
  Bell,
  PanelLeftClose,
  PanelLeft,
} from "lucide-react";
import { useUiStore } from "@/store/ui";
import { cn } from "@/utils/helpers";

const NAV_ITEMS = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard", end: true },
  { to: "/workflows", icon: Workflow, label: "Workflows" },
  { to: "/souls", icon: Bot, label: "Souls" },
  { to: "/tasks", icon: ListTodo, label: "Tasks" },
  { to: "/steps", icon: CheckSquare, label: "Steps" },
  { to: "/runs", icon: Play, label: "Runs" },
] as const;

const BOTTOM_NAV = [
  { to: "/settings", icon: Settings, label: "Settings" },
] as const;

function pageTitleFromPath(pathname: string): string {
  const segment = pathname.split("/").filter(Boolean)[0] ?? "dashboard";
  return segment.charAt(0).toUpperCase() + segment.slice(1);
}

export function ShellLayout() {
  const sidebarOpen = useUiStore((s) => s.sidebarOpen);
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const { data: providersData } = useProviders();
  const providerCount = providersData?.total ?? 0;
  const location = useLocation();

  return (
    <div className="h-screen flex overflow-hidden bg-background text-foreground">
      {/* Sidebar */}
      <aside
        className={cn(
          "flex flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-200",
          sidebarOpen ? "w-[240px]" : "w-[52px]",
        )}
      >
        {/* Logo */}
        <div className="h-12 px-3 border-b border-sidebar-border flex items-center gap-2 shrink-0">
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            className="shrink-0"
          >
            <circle cx="12" cy="5" r="2.5" fill="var(--primary)" />
            <circle
              cx="5"
              cy="17"
              r="2.5"
              fill="var(--primary)"
              opacity="0.7"
            />
            <circle
              cx="19"
              cy="17"
              r="2.5"
              fill="var(--primary)"
              opacity="0.7"
            />
            <circle
              cx="12"
              cy="13"
              r="1.5"
              fill="var(--primary)"
              opacity="0.5"
            />
            <line
              x1="12"
              y1="7.5"
              x2="12"
              y2="11.5"
              stroke="var(--primary)"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
            <line
              x1="10.8"
              y1="14"
              x2="6.5"
              y2="15.5"
              stroke="var(--primary)"
              strokeWidth="1.5"
              strokeLinecap="round"
              opacity="0.6"
            />
            <line
              x1="13.2"
              y1="14"
              x2="17.5"
              y2="15.5"
              stroke="var(--primary)"
              strokeWidth="1.5"
              strokeLinecap="round"
              opacity="0.6"
            />
          </svg>
          {sidebarOpen && (
            <span className="text-[13px] font-semibold tracking-[0.08em] uppercase text-foreground">
              Runsight
            </span>
          )}
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
                  "flex items-center gap-3 h-9 px-3 rounded-md text-sm transition-colors",
                  isActive
                    ? "bg-primary/12 text-primary"
                    : "text-muted-foreground hover:bg-surface-elevated hover:text-foreground",
                )
              }
            >
              <Icon className="size-[18px] shrink-0" strokeWidth={1.5} />
              {sidebarOpen && <span>{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Bottom nav */}
        <div className="p-2 border-t border-sidebar-border">
          {BOTTOM_NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 h-9 px-3 rounded-md text-sm transition-colors",
                  isActive
                    ? "bg-primary/12 text-primary"
                    : "text-muted-foreground hover:bg-surface-elevated hover:text-foreground",
                )
              }
            >
              <Icon className="size-[18px] shrink-0" strokeWidth={1.5} />
              {sidebarOpen && <span>{label}</span>}
            </NavLink>
          ))}
        </div>
      </aside>

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="h-12 bg-card border-b border-border flex items-center justify-between px-4 shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={toggleSidebar}
              className="size-8 flex items-center justify-center rounded-md hover:bg-surface-elevated text-muted-foreground hover:text-foreground transition-colors"
            >
              {sidebarOpen ? (
                <PanelLeftClose className="size-[18px]" strokeWidth={1.5} />
              ) : (
                <PanelLeft className="size-[18px]" strokeWidth={1.5} />
              )}
            </button>
            <h1 className="text-base font-medium tracking-tight">
              {pageTitleFromPath(location.pathname)}
            </h1>
          </div>

          <div className="flex items-center gap-1">
            <button className="size-8 flex items-center justify-center rounded-md hover:bg-surface-elevated text-muted-foreground hover:text-foreground transition-colors">
              <Search className="size-[18px]" strokeWidth={1.5} />
            </button>
            <button className="size-8 flex items-center justify-center rounded-md hover:bg-surface-elevated text-muted-foreground hover:text-foreground transition-colors">
              <Bell className="size-[18px]" strokeWidth={1.5} />
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 flex flex-col overflow-y-auto">
          <RouteErrorBoundary>
            <Outlet />
          </RouteErrorBoundary>
        </main>

        {/* Bottom bar */}
        <footer className="h-7 bg-card border-t border-border flex items-center px-4 text-xs text-muted-foreground shrink-0">
          <span>Runsight v0.1.0</span>
          <span className="mx-2 text-border">|</span>
          <span className="flex items-center gap-1.5">
            <span className={`size-1.5 rounded-full ${providerCount > 0 ? "bg-success" : "bg-muted-foreground"}`} />
            {providerCount > 0
              ? `${providerCount} provider${providerCount > 1 ? "s" : ""} connected`
              : "No providers configured"}
          </span>
        </footer>
      </div>
    </div>
  );
}
