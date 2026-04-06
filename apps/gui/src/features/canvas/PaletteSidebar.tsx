import { useState } from "react";
import {
  ArrowRightLeft,
  GitFork,
  Code,
  ChevronLeft,
  User,
} from "lucide-react";
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from "@runsight/ui/tooltip";
import { useSouls } from "@/queries/souls";

const BLOCK_TYPES = [
  { label: "Linear", icon: ArrowRightLeft },
  { label: "Gate", icon: GitFork },
  { label: "Code", icon: Code },
] as const;

interface PaletteSidebarProps {
  onCollapse?: (collapsed: boolean) => void;
  dimmed?: boolean;
  interactive?: boolean;
}

export function PaletteSidebar({ onCollapse, dimmed = false, interactive = true }: PaletteSidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [search, setSearch] = useState("");
  const { data: souls } = useSouls();

  const width = isCollapsed ? 48 : 240;
  const soulItems = souls?.items ?? [];

  const filteredBlocks = BLOCK_TYPES.filter((b) =>
    b.label.toLowerCase().includes(search.toLowerCase()),
  );

  const filteredSouls = soulItems.filter((soul) =>
    (soul.role ?? "").toLowerCase().includes(search.toLowerCase()),
  );

  function handleToggleCollapse() {
    setIsCollapsed((prev) => {
      const next = !prev;
      onCollapse?.(next);
      return next;
    });
    setSearch("");
  }

  return (
    <aside
      className={`flex flex-col bg-surface-secondary border-r border-border-subtle overflow-y-auto shrink-0${dimmed ? " opacity-50" : ""}${!interactive ? " pointer-events-none" : ""}`}
      style={{ width, gridColumn: "1", gridRow: "2" }}
    >
      {/* Header with title + notch button */}
      <div
        className={`flex items-center h-[var(--header-height)] border-b border-border-subtle shrink-0 ${isCollapsed ? "justify-center p-0" : "justify-between px-3 py-0"}`}
      >
        {!isCollapsed && (
          <span className="text-lg font-medium text-heading">
            Palette
          </span>
        )}
        <button
          onClick={handleToggleCollapse}
          className="flex items-center justify-center w-5 h-5 bg-transparent border-none text-muted cursor-pointer rounded-sm text-xs hover:text-primary hover:bg-surface-hover"
          aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!isCollapsed}
        >
          <ChevronLeft
            size={12}
            className={isCollapsed ? "rotate-180" : ""}
          />
        </button>
      </div>

      {/* Search input — hidden when collapsed */}
      {!isCollapsed && (
        <input type="search" placeholder="Search blocks..." value={search} onChange={(e) => setSearch(e.target.value)} className="mx-3 my-3 h-[var(--control-height-sm)] px-3 bg-surface-tertiary border border-border-subtle rounded-md text-primary text-sm outline-none placeholder:text-muted focus:border-border-focus" style={{ width: "calc(100% - var(--space-3) * 2)" }} />
      )}

      {/* Block types section */}
      <div>
        {!isCollapsed && (
          <span
            className="block px-3 py-2 font-mono text-2xs font-semibold text-muted uppercase tracking-widest"
          >
            Blocks
          </span>
        )}
        <TooltipProvider>
          {filteredBlocks.map(({ label, icon: Icon }) =>
            isCollapsed ? ( // isCollapsed — show Tooltip
              <Tooltip key={label}>
                <TooltipTrigger
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.effectAllowed = "copy";
                    e.dataTransfer.setData(
                      "application/runsight-block",
                      JSON.stringify({ type: "block", label }),
                    );
                  }}
                  className="flex items-center justify-center h-9 w-full rounded-md text-primary hover:bg-surface-hover cursor-grab"
                >
                  <Icon size={18} className="shrink-0" />
                </TooltipTrigger>
                <TooltipContent side="right">{label}</TooltipContent>
              </Tooltip>
            ) : (
              <div
                key={label}
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.effectAllowed = "copy";
                  e.dataTransfer.setData(
                    "application/runsight-block",
                    JSON.stringify({ type: "block", label }),
                  );
                }}
                className="flex items-center gap-2 h-11 px-3 mx-1 rounded-md text-sm text-primary hover:bg-surface-hover cursor-grab"
              >
                <Icon size={18} className="shrink-0" />
                <span>{label}</span>
              </div>
            ),
          )}
        </TooltipProvider>
      </div>

      {/* Section divider */}
      <div className="border-t border-border-subtle mx-2" />

      {/* Souls section */}
      <div>
        {!isCollapsed && (
          <span
            className="block px-3 py-2 font-mono text-2xs font-semibold text-muted uppercase tracking-widest"
          >
            Souls
          </span>
        )}
        <TooltipProvider>
          {filteredSouls.map((soul) =>
            isCollapsed ? (
              <Tooltip key={soul.id}>
                <TooltipTrigger
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.effectAllowed = "copy";
                    e.dataTransfer.setData(
                      "application/runsight-soul",
                      JSON.stringify({ type: "soul", label: soul.role ?? soul.id }),
                    );
                  }}
                  className="flex items-center justify-center h-9 w-full rounded-md text-primary hover:bg-surface-hover cursor-grab"
                >
                  <User size={18} className="shrink-0" />
                </TooltipTrigger>
                <TooltipContent side="right">{soul.role ?? soul.id}</TooltipContent>
              </Tooltip>
            ) : (
              <div
                key={soul.id}
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.effectAllowed = "copy";
                  e.dataTransfer.setData(
                    "application/runsight-soul",
                    JSON.stringify({ type: "soul", label: soul.role ?? soul.id }),
                  );
                }}
                className="flex items-center gap-2 h-11 px-3 mx-1 rounded-md text-sm text-primary hover:bg-surface-hover cursor-grab"
              >
                <User size={18} className="shrink-0" />
                <span>{soul.role ?? soul.id}</span>
              </div>
            ),
          )}
        </TooltipProvider>
      </div>
    </aside>
  );
}
