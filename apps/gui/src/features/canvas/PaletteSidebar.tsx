import { useState } from "react";
import {
  ArrowRightLeft,
  GitFork,
  Code,
  FileOutput,
  ChevronLeft,
  User,
} from "lucide-react";
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from "@runsight/ui/tooltip";
import { useSouls } from "@/queries/souls";

const BLOCK_TYPES = [
  { label: "Linear", icon: ArrowRightLeft },
  { label: "Gate", icon: GitFork },
  { label: "Code", icon: Code },
  { label: "FileWriter", icon: FileOutput },
] as const;

export function PaletteSidebar() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [search, setSearch] = useState("");
  const { data: souls } = useSouls();

  const width = isCollapsed ? 48 : 240;
  const soulItems = souls?.items ?? [];

  const filteredBlocks = BLOCK_TYPES.filter((b) =>
    b.label.toLowerCase().includes(search.toLowerCase()),
  );

  const filteredSouls = soulItems.filter((soul) =>
    (soul.name ?? "").toLowerCase().includes(search.toLowerCase()),
  );

  function handleToggleCollapse() {
    setIsCollapsed((prev) => !prev);
    setSearch("");
  }

  return (
    <aside
      className="flex flex-col bg-[var(--surface-secondary)] border-r border-[var(--border-subtle)] overflow-y-auto shrink-0"
      style={{ width, gridColumn: "1", gridRow: "2" }}
    >
      {/* Header with title + notch button */}
      <div
        className="flex items-center justify-between h-[var(--header-height)] border-b border-[var(--border-subtle)] shrink-0"
        style={{ padding: isCollapsed ? "0" : "0 var(--space-3)", justifyContent: isCollapsed ? "center" : "space-between" }}
      >
        {!isCollapsed && (
          <span className="text-[var(--font-size-lg)] font-medium text-[var(--text-heading)]">
            Palette
          </span>
        )}
        <button
          onClick={handleToggleCollapse}
          className="flex items-center justify-center w-5 h-5 bg-transparent border-none text-[var(--text-muted)] cursor-pointer rounded-[var(--radius-sm)] text-xs hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)]"
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
        <input type="search" placeholder="Search blocks..." value={search} onChange={(e) => setSearch(e.target.value)} className="mx-[var(--space-3)] my-[var(--space-3)] h-[var(--control-height-sm)] px-[var(--space-3)] bg-[var(--surface-tertiary)] border border-[var(--border-subtle)] rounded-[var(--radius-md)] text-[var(--text-primary)] text-[var(--font-size-sm)] outline-none placeholder:text-[var(--text-muted)] focus:border-[var(--border-focus)]" style={{ width: "calc(100% - var(--space-3) * 2)" }} />
      )}

      {/* Block types section */}
      <div>
        {!isCollapsed && (
          <span
            className="block px-[var(--space-3)] py-[var(--space-2)] font-mono text-[var(--font-size-2xs)] font-semibold text-[var(--text-muted)] uppercase"
            style={{ letterSpacing: "var(--tracking-wider)" }}
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
                  className="flex items-center justify-center h-9 w-full rounded-[var(--radius-md)] text-[var(--text-primary)] hover:bg-[var(--surface-hover)] cursor-grab"
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
                className="flex items-center gap-[var(--space-2)] h-11 px-[var(--space-3)] mx-[var(--space-1)] rounded-[var(--radius-md)] text-[var(--font-size-sm)] text-[var(--text-primary)] hover:bg-[var(--surface-hover)] cursor-grab"
              >
                <Icon size={18} className="shrink-0" />
                <span>{label}</span>
              </div>
            ),
          )}
        </TooltipProvider>
      </div>

      {/* Section divider */}
      <div className="border-t border-(--border-subtle) mx-[var(--space-2)]" />

      {/* Souls section */}
      <div>
        {!isCollapsed && (
          <span
            className="block px-[var(--space-3)] py-[var(--space-2)] font-mono text-[var(--font-size-2xs)] font-semibold text-[var(--text-muted)] uppercase"
            style={{ letterSpacing: "var(--tracking-wider)" }}
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
                      JSON.stringify({ type: "soul", label: soul.name }),
                    );
                  }}
                  className="flex items-center justify-center h-9 w-full rounded-[var(--radius-md)] text-[var(--text-primary)] hover:bg-[var(--surface-hover)] cursor-grab"
                >
                  <User size={18} className="shrink-0" />
                </TooltipTrigger>
                <TooltipContent side="right">{soul.name}</TooltipContent>
              </Tooltip>
            ) : (
              <div
                key={soul.id}
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.effectAllowed = "copy";
                  e.dataTransfer.setData(
                    "application/runsight-soul",
                    JSON.stringify({ type: "soul", label: soul.name }),
                  );
                }}
                className="flex items-center gap-[var(--space-2)] h-11 px-[var(--space-3)] mx-[var(--space-1)] rounded-[var(--radius-md)] text-[var(--font-size-sm)] text-[var(--text-primary)] hover:bg-[var(--surface-hover)] cursor-grab"
              >
                <User size={18} className="shrink-0" />
                <span>{soul.name}</span>
              </div>
            ),
          )}
        </TooltipProvider>
      </div>
    </aside>
  );
}
