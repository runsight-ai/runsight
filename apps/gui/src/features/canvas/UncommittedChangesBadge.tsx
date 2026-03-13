import { Button } from "@/components/ui/button";
import { GitCommit } from "lucide-react";

interface UncommittedChangesBadgeProps {
  count: number;
  onClick: () => void;
  disabled?: boolean;
}

export function UncommittedChangesBadge({
  count,
  onClick,
  disabled = false,
}: UncommittedChangesBadgeProps) {
  return (
    <div className="flex items-center gap-2">
      {/* Badge */}
      <div className="flex items-center gap-1.5 h-6 px-2.5 rounded bg-[#F5A623]/10 border border-[#F5A623]/30">
        <span className="w-2 h-2 rounded-full bg-[#F5A623] animate-pulse" />
        <span className="text-[11px] font-medium text-[#F5A623]">
          {count} uncommitted
        </span>
      </div>

      {/* Commit Button */}
      <Button
        variant="outline"
        size="sm"
        className="h-8 px-3 border-[#3F3F4A] bg-transparent text-[#EDEDF0] hover:bg-[#22222A] hover:text-[#EDEDF0] flex items-center gap-1.5"
        onClick={onClick}
        disabled={disabled}
        aria-label={`Commit ${count} uncommitted change${count !== 1 ? "s" : ""}`}
      >
        <GitCommit className="w-4 h-4" />
        <span className="text-sm">Commit</span>
      </Button>
    </div>
  );
}
