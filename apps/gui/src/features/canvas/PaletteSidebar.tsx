import { useState } from "react";
import {
  ArrowRightLeft,
  GitFork,
  Code,
  FileOutput,
  ChevronLeft,
  User,
} from "lucide-react";
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from "@/components/ui/tooltip";
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
      className="flex flex-col border-r border-border bg-(--neutral-1) overflow-y-auto shrink-0"
      style={{ width }}
    >
      {/* Toggle / notch button with chevron */}
      <div className="flex justify-end p-1">
        <button
          onClick={handleToggleCollapse}
          className="p-1 rounded hover:bg-(--neutral-3) text-(--text-secondary)"
          aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <ChevronLeft
            size={16}
            className={isCollapsed ? "rotate-180" : ""}
          />
        </button>
      </div>

      {/* Search input — hidden when collapsed */}
      {!isCollapsed && (
        <div className="px-2 pb-2">
          <input type="text" placeholder="Search..." value={search} onChange={(e) => setSearch(e.target.value)} className="w-full px-2 py-1 rounded text-sm border border-border bg-(--neutral-1) text-(--text-primary) placeholder:text-(--text-muted)" />
        </div>
      )}

      {/* Block types section */}
      <div className="px-2 pb-2">
        {!isCollapsed && (
          <span className="text-xs font-medium text-(--text-muted) px-1 mb-1 block">
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
                  className="flex items-center gap-2 w-full px-2 py-1.5 rounded text-sm text-(--text-primary) hover:bg-(--neutral-3) cursor-grab"
                >
                  <Icon size={16} className="shrink-0" />
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
                className="flex items-center gap-2 w-full px-2 py-1.5 rounded text-sm text-(--text-primary) hover:bg-(--neutral-3) cursor-grab"
              >
                <Icon size={16} className="shrink-0" />
                <span>{label}</span>
              </div>
            ),
          )}
        </TooltipProvider>
      </div>

      {/* Divider */}
      <div className="border-t border-border mx-2" />

      {/* Souls section */}
      <div className="px-2 pt-2">
        {!isCollapsed && (
          <span className="text-xs font-medium text-(--text-muted) px-1 mb-1 block">
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
                  className="flex items-center gap-2 w-full px-2 py-1.5 rounded text-sm text-(--text-primary) hover:bg-(--neutral-3) cursor-grab"
                >
                  <User size={16} className="shrink-0" />
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
                className="flex items-center gap-2 w-full px-2 py-1.5 rounded text-sm text-(--text-primary) hover:bg-(--neutral-3) cursor-grab"
              >
                <User size={16} className="shrink-0" />
                <span>{soul.name}</span>
              </div>
            ),
          )}
        </TooltipProvider>
      </div>
    </aside>
  );
}
