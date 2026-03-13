import { useEffect, useState, useCallback } from "react";
import { X, CheckCircle, AlertCircle } from "lucide-react";
import { cn } from "@/utils/helpers";

export interface SummaryToastProps {
  isOpen: boolean;
  duration: string;
  cost: number;
  status: "success" | "failed" | "partial";
  onClose: () => void;
  autoDismissMs?: number;
}

const statusConfig = {
  success: {
    borderColor: "border-l-[#28A745]",
    iconColor: "text-[#28A745]",
    iconBg: "bg-[rgba(40,167,69,0.2)]",
    statusText: "Success",
    Icon: CheckCircle,
  },
  failed: {
    borderColor: "border-l-[#E53935]",
    iconColor: "text-[#E53935]",
    iconBg: "bg-[rgba(229,57,53,0.2)]",
    statusText: "Failed",
    Icon: AlertCircle,
  },
  partial: {
    borderColor: "border-l-[#F5A623]",
    iconColor: "text-[#F5A623]",
    iconBg: "bg-[rgba(245,166,35,0.2)]",
    statusText: "Partial Success",
    Icon: AlertCircle,
  },
};

export function SummaryToast({
  isOpen,
  duration,
  cost,
  status,
  onClose,
  autoDismissMs = 8000,
}: SummaryToastProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [isFading, setIsFading] = useState(false);

  const handleClose = useCallback(() => {
    setIsFading(true);
    setTimeout(() => {
      setIsVisible(false);
      setIsFading(false);
      onClose();
    }, 300);
  }, [onClose]);

  useEffect(() => {
    if (isOpen) {
      setIsFading(false);
      setIsVisible(true);
    }
  }, [isOpen]);

  // Auto-dismiss effect
  useEffect(() => {
    if (!isVisible || !isOpen) return;

    const timer = setTimeout(() => {
      handleClose();
    }, autoDismissMs);

    return () => {
      clearTimeout(timer);
    };
  }, [isVisible, isOpen, autoDismissMs, handleClose]);

  if (!isVisible && !isOpen) return null;

  const config = statusConfig[status];
  const { Icon } = config;

  return (
    <div
      className={cn(
        "fixed bottom-4 right-4 z-[90] w-[360px] max-w-[360px]",
        "transition-all duration-300 ease-out",
        isFading ? "opacity-0 translate-y-2" : "opacity-100 translate-y-0"
      )}
    >
      <div
        className={cn(
          "flex items-center gap-3 px-4 py-3 rounded-lg",
          "bg-[#22222A] border border-[#2D2D35] shadow-[0_4px_12px_rgba(0,0,0,0.4)]",
          "border-l-[3px]",
          config.borderColor
        )}
      >
        {/* Icon */}
        <div
          className={cn(
            "w-8 h-8 rounded-full flex items-center justify-center shrink-0",
            config.iconBg
          )}
        >
          <Icon className={cn("w-4 h-4", config.iconColor)} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-[#EDEDF0]">
            Run complete
          </div>
          <div className="text-xs text-[#9292A0]">
            {duration} · ${cost.toFixed(3)} · {config.statusText}
          </div>
        </div>

        {/* Close Button */}
        <button
          onClick={handleClose}
          className={cn(
            "w-6 h-6 flex items-center justify-center rounded",
            "text-[#9292A0] hover:text-[#EDEDF0] hover:bg-[#16161C]",
            "transition-colors shrink-0"
          )}
          aria-label="Close toast"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

export default SummaryToast;
