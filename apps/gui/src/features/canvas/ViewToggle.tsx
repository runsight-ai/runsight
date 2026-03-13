import { cn } from "@/utils/helpers";
import { Code, Layout } from "lucide-react";

export type ViewMode = "visual" | "code";

interface ViewToggleProps {
  mode: ViewMode;
  onChange: (mode: ViewMode) => void;
  disabled?: boolean;
  disableReason?: string;
}

export function ViewToggle({
  mode,
  onChange,
  disabled = false,
  disableReason,
}: ViewToggleProps) {
  return (
    <div
      className={cn(
        "h-8 bg-[#16161C] border border-[#2D2D35] rounded-md flex items-center p-0.5",
        disabled && "opacity-60 cursor-not-allowed"
      )}
      title={disabled && disableReason ? disableReason : undefined}
    >
      <button
        onClick={() => !disabled && onChange("visual")}
        disabled={disabled}
        aria-pressed={mode === "visual"}
        className={cn(
          "px-3 h-7 rounded text-xs font-medium flex items-center gap-1.5 transition-all duration-150",
          mode === "visual"
            ? "text-[#EDEDF0] bg-[#22222A]"
            : "text-[#9292A0] hover:text-[#EDEDF0] hover:bg-[#22222A]/50"
        )}
      >
        <Layout className="w-3.5 h-3.5" />
        Visual
      </button>
      <button
        onClick={() => !disabled && onChange("code")}
        disabled={disabled}
        aria-pressed={mode === "code"}
        className={cn(
          "px-3 h-7 rounded text-xs font-medium flex items-center gap-1.5 transition-all duration-150",
          mode === "code"
            ? "text-[#EDEDF0] bg-[#5E6AD2]"
            : "text-[#9292A0] hover:text-[#EDEDF0] hover:bg-[#22222A]/50"
        )}
      >
        <Code className="w-3.5 h-3.5" />
        Code
      </button>
    </div>
  );
}

// Simple segmented control variant without icons
export function ViewToggleSimple({
  mode,
  onChange,
  disabled = false,
}: ViewToggleProps) {
  return (
    <div
      className={cn(
        "h-8 bg-[#16161C] border border-[#2D2D35] rounded-md flex items-center p-0.5",
        disabled && "opacity-60 cursor-not-allowed"
      )}
    >
      <button
        onClick={() => !disabled && onChange("visual")}
        disabled={disabled}
        className={cn(
          "px-3 h-7 rounded text-xs font-medium transition-all duration-150",
          mode === "visual"
            ? "text-[#EDEDF0] bg-[#22222A]"
            : "text-[#9292A0] hover:text-[#EDEDF0]"
        )}
      >
        Visual
      </button>
      <button
        onClick={() => !disabled && onChange("code")}
        disabled={disabled}
        className={cn(
          "px-3 h-7 rounded text-xs font-medium transition-all duration-150",
          mode === "code"
            ? "text-[#EDEDF0] bg-[#5E6AD2]"
            : "text-[#9292A0] hover:text-[#EDEDF0]"
        )}
      >
        Code
      </button>
    </div>
  );
}
