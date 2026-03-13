import { useState, useEffect } from "react";
import {
  ChevronDown,
  ChevronRight,
  Search,
  X,
  User,
  GitBranch,
  MessageSquare,
  Radio,
  GitFork,
  Shield,
  Merge,
  Layers,
  RotateCcw,
  Crown,
  Briefcase,
  Box,
  FileOutput,
} from "lucide-react";
import { cn } from "@/utils/helpers";
import type { StepType } from "@/types/schemas/canvas";

export interface PaletteItem {
  id: string;
  name: string;
  subtitle?: string;
  iconColor: string;
  type: StepType;
}

const STEP_TYPE_ICONS: Record<StepType, React.ComponentType<{ className?: string; style?: React.CSSProperties }>> = {
  linear: User,
  fanout: GitBranch,
  debate: MessageSquare,
  message_bus: Radio,
  router: GitFork,
  gate: Shield,
  synthesize: Merge,
  workflow: Layers,
  retry: RotateCcw,
  team_lead: Crown,
  engineering_manager: Briefcase,
  placeholder: Box,
  file_writer: FileOutput,
};

/** Step type palette catalog grouped by category (spec §3.3) */
const STEP_PALETTE: { title: string; items: PaletteItem[] }[] = [
  {
    title: "Basic",
    items: [
      { id: "linear", name: "Linear", subtitle: "Single agent, single task", iconColor: "#5E6AD2", type: "linear" },
      { id: "placeholder", name: "Placeholder", subtitle: "No-op / stub", iconColor: "#5E5E6B", type: "placeholder" },
    ],
  },
  {
    title: "Multi-Agent",
    items: [
      { id: "fanout", name: "Fan Out", subtitle: "Parallel execution across agents", iconColor: "#28A745", type: "fanout" },
      { id: "debate", name: "Debate", subtitle: "Two agents argue, iterate", iconColor: "#F5A623", type: "debate" },
      { id: "message_bus", name: "Message Bus", subtitle: "Broadcast + collect from N agents", iconColor: "#E53935", type: "message_bus" },
      { id: "synthesize", name: "Synthesize", subtitle: "Merge outputs from multiple blocks", iconColor: "#5E6AD2", type: "synthesize" },
      { id: "team_lead", name: "Team Lead", subtitle: "Orchestrator with failure handling", iconColor: "#28A745", type: "team_lead" },
      { id: "engineering_manager", name: "Engineering Manager", subtitle: "Senior orchestrator", iconColor: "#F5A623", type: "engineering_manager" },
    ],
  },
  {
    title: "Flow Control",
    items: [
      { id: "router", name: "Router", subtitle: "Conditional branching", iconColor: "#5E6AD2", type: "router" },
      { id: "gate", name: "Gate", subtitle: "Binary pass/fail evaluation", iconColor: "#28A745", type: "gate" },
      { id: "retry", name: "Retry", subtitle: "Wrap block with retry logic", iconColor: "#F5A623", type: "retry" },
    ],
  },
  {
    title: "Integration",
    items: [
      { id: "workflow", name: "Workflow", subtitle: "Nested sub-workflow", iconColor: "#5E6AD2", type: "workflow" },
      { id: "file_writer", name: "File Writer", subtitle: "Write output to file", iconColor: "#9292A0", type: "file_writer" },
    ],
  },
];

interface CollapsibleSectionProps {
  title: string;
  isOpen: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

function CollapsibleSection({ title, isOpen, onToggle, children }: CollapsibleSectionProps) {
  return (
    <div className="mb-2">
      <button
        onClick={onToggle}
        className="w-full h-8 px-2 flex items-center gap-2 rounded-md hover:bg-[#22222A] text-[#9292A0] text-sm transition-colors"
      >
        {isOpen ? (
          <ChevronDown className="w-3 h-3" />
        ) : (
          <ChevronRight className="w-3 h-3" />
        )}
        <span className="text-[11px] font-semibold uppercase tracking-[0.08em]">{title}</span>
      </button>
      {isOpen && <div className="mt-1 space-y-1">{children}</div>}
    </div>
  );
}

interface PaletteItemProps {
  item: PaletteItem;
  onDragStart: (e: React.DragEvent, item: PaletteItem) => void;
}

function PaletteItemRow({ item, onDragStart }: PaletteItemProps) {
  const Icon = STEP_TYPE_ICONS[item.type];
  return (
    <div
      draggable
      onDragStart={(e) => onDragStart(e, item)}
      className="h-11 px-3 rounded-md flex items-center gap-3 cursor-grab hover:bg-[#22222A] transition-colors active:cursor-grabbing"
    >
      <div
        className="w-5 h-5 rounded-full flex items-center justify-center"
        style={{ backgroundColor: `${item.iconColor}20` }}
      >
        <Icon className="w-3 h-3" style={{ color: item.iconColor }} />
      </div>
      <div>
        <div className="text-sm text-[#EDEDF0]">{item.name}</div>
        {item.subtitle && (
          <div className="text-xs text-[#5E5E6B]">{item.subtitle}</div>
        )}
      </div>
    </div>
  );
}

interface CanvasSidebarProps {
  onClose?: () => void;
  onDragStart?: (e: React.DragEvent, item: PaletteItem) => void;
  pulseAnimation?: boolean;
  isCollapsed?: boolean;
}

export function CanvasSidebar({ onClose, onDragStart, pulseAnimation = false, isCollapsed = false }: CanvasSidebarProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [basicOpen, setBasicOpen] = useState(true);
  const [multiAgentOpen, setMultiAgentOpen] = useState(true);
  const [flowControlOpen, setFlowControlOpen] = useState(true);
  const [integrationOpen, setIntegrationOpen] = useState(true);
  const [isPulsing, setIsPulsing] = useState(false);

  // Pulse animation after 3 seconds of inactivity
  useEffect(() => {
    if (!pulseAnimation) return;

    const timer = setTimeout(() => {
      setIsPulsing(true);
      setTimeout(() => setIsPulsing(false), 600);
    }, 3000);

    return () => clearTimeout(timer);
  }, [pulseAnimation]);

  const handleDragStart = (e: React.DragEvent, item: PaletteItem) => {
    e.dataTransfer.setData("application/json", JSON.stringify(item));
    e.dataTransfer.effectAllowed = "copy";
    onDragStart?.(e, item);
  };

  // Filter palette items by search
  const filterItems = (items: PaletteItem[]) => {
    if (!searchQuery.trim()) return items;
    const q = searchQuery.toLowerCase();
    return items.filter(
      (item) =>
        item.name.toLowerCase().includes(q) ||
        item.subtitle?.toLowerCase().includes(q) ||
        item.type.replace(/_/g, " ").includes(q)
    );
  };

  if (isCollapsed) {
    return (
      <aside className="w-12 bg-[#16161C] border-r border-[#2D2D35] flex flex-col items-center py-3 z-50">
        {/* Logo (small) */}
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="mb-4">
          <circle cx="12" cy="5" r="2.5" fill="#5E6AD2"/>
          <circle cx="5" cy="17" r="2.5" fill="#5E6AD2" opacity="0.7"/>
          <circle cx="19" cy="17" r="2.5" fill="#5E6AD2" opacity="0.7"/>
          <circle cx="12" cy="13" r="1.5" fill="#5E6AD2" opacity="0.5"/>
          <line x1="12" y1="7.5" x2="12" y2="11.5" stroke="#5E6AD2" strokeWidth="1.5" strokeLinecap="round"/>
          <line x1="10.8" y1="14" x2="6.5" y2="15.5" stroke="#5E6AD2" strokeWidth="1.5" strokeLinecap="round" opacity="0.6"/>
          <line x1="13.2" y1="14" x2="17.5" y2="15.5" stroke="#5E6AD2" strokeWidth="1.5" strokeLinecap="round" opacity="0.6"/>
        </svg>

        {/* Active indicator */}
        <div className="w-8 h-8 flex items-center justify-center rounded-md bg-[#5E6AD2]/10 text-[#5E6AD2]">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="2" y="3" width="20" height="6" rx="2"/>
            <rect x="2" y="15" width="20" height="6" rx="2"/>
          </svg>
        </div>
      </aside>
    );
  }

  return (
    <aside
      className={cn(
        "w-[240px] bg-[#16161C] border-r border-[#2D2D35] flex flex-col z-50 transition-colors duration-300",
        isPulsing && "bg-[#22222A]"
      )}
    >
      {/* Logo Header */}
      <div className="h-12 px-3 border-b border-[#2D2D35] flex items-center gap-2">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="12" cy="5" r="2.5" fill="#5E6AD2"/>
          <circle cx="5" cy="17" r="2.5" fill="#5E6AD2" opacity="0.7"/>
          <circle cx="19" cy="17" r="2.5" fill="#5E6AD2" opacity="0.7"/>
          <circle cx="12" cy="13" r="1.5" fill="#5E6AD2" opacity="0.5"/>
          <line x1="12" y1="7.5" x2="12" y2="11.5" stroke="#5E6AD2" strokeWidth="1.5" strokeLinecap="round"/>
          <line x1="10.8" y1="14" x2="6.5" y2="15.5" stroke="#5E6AD2" strokeWidth="1.5" strokeLinecap="round" opacity="0.6"/>
          <line x1="13.2" y1="14" x2="17.5" y2="15.5" stroke="#5E6AD2" strokeWidth="1.5" strokeLinecap="round" opacity="0.6"/>
        </svg>
        <span className="text-[13px] font-semibold tracking-[0.08em] uppercase text-[#EDEDF0]">RUNSIGHT</span>
      </div>

      {/* Palette Header */}
      <div className="h-10 px-3 flex items-center justify-between border-b border-[#2D2D35]">
        <span className="text-sm font-medium text-[#EDEDF0]">Palette</span>
        {onClose && (
          <button
            onClick={onClose}
            className="w-6 h-6 flex items-center justify-center rounded hover:bg-[#22222A] text-[#9292A0] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Search */}
      <div className="p-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#5E5E6B]" />
          <input
            type="text"
            placeholder="Search..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-9 bg-[#0D0D12] border border-[#2D2D35] rounded-md pl-9 pr-3 text-sm text-[#EDEDF0] placeholder:text-[#5E5E6B] focus:outline-none focus:border-[#5E6AD2] transition-colors"
            aria-label="Search palette items"
          />
        </div>
      </div>

      {/* Palette Sections */}
      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {STEP_PALETTE.map((section) => {
          const filtered = filterItems(section.items);
          return (
            <CollapsibleSection
              key={section.title}
              title={section.title}
              isOpen={
                section.title === "Basic"
                  ? basicOpen
                  : section.title === "Multi-Agent"
                    ? multiAgentOpen
                    : section.title === "Flow Control"
                      ? flowControlOpen
                      : integrationOpen
              }
              onToggle={() => {
                if (section.title === "Basic") setBasicOpen((o) => !o);
                else if (section.title === "Multi-Agent") setMultiAgentOpen((o) => !o);
                else if (section.title === "Flow Control") setFlowControlOpen((o) => !o);
                else setIntegrationOpen((o) => !o);
              }}
            >
              {filtered.length === 0 ? (
                <div className="px-3 py-2 text-xs text-[#5E5E6B]">No matching steps</div>
              ) : (
                filtered.map((item) => (
                  <PaletteItemRow key={item.id} item={item} onDragStart={handleDragStart} />
                ))
              )}
            </CollapsibleSection>
          );
        })}
      </div>
    </aside>
  );
}
