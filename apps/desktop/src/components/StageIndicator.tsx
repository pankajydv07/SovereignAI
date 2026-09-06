import React from "react";
import { Activity } from "lucide-react";

interface StageIndicatorProps {
  label: string;
  elapsedMs?: number;
  className?: string;
}

export const StageIndicator: React.FC<StageIndicatorProps> = ({
  label,
  elapsedMs = 0,
  className = "",
}) => {
  const seconds = (elapsedMs / 1000).toFixed(1);

  return (
    <div
      className={`inline-flex items-center gap-2 px-3 py-1.5 bg-surface-2 border border-border rounded-sm font-mono text-xs text-text ${className}`}
    >
      <Activity className="w-3.5 h-3.5 text-accent animate-pulse" />
      <span className="font-semibold text-text">{label}</span>
      <span className="text-[11px] text-text-dim ml-1">· {seconds}s</span>
    </div>
  );
};
