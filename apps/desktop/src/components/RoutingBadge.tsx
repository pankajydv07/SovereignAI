import React from "react";

export interface RoutingBadgeProps {
  role: string;
  model: string;
  confidence?: number;
  latencySeconds?: number;
  className?: string;
}

const ROLE_TINTS: Record<string, { border: string; text: string; dot: string }> = {
  planner: {
    border: "border-[#6366F1]",
    text: "text-[#818CF8]",
    dot: "bg-[#6366F1]",
  },
  coder: {
    border: "border-[#8B5CF6]",
    text: "text-[#A78BFA]",
    dot: "bg-[#8B5CF6]",
  },
  vision: {
    border: "border-[#06B6D4]",
    text: "text-[#22D3EE]",
    dot: "bg-[#06B6D4]",
  },
  writer: {
    border: "border-[#8B5CF6]",
    text: "text-[#A78BFA]",
    dot: "bg-[#8B5CF6]",
  },
};

export const RoutingBadge: React.FC<RoutingBadgeProps> = ({
  role,
  model,
  confidence = 0.98,
  latencySeconds,
  className = "",
}) => {
  const tint = ROLE_TINTS[role.toLowerCase()] || ROLE_TINTS.writer;
  const latencyDisplay = latencySeconds !== undefined ? `${latencySeconds.toFixed(1)}s` : null;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded border text-[11px] font-mono bg-surface-2 ${tint.border} ${tint.text} ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${tint.dot}`} />
      <span>{model}</span>
      <span className="text-text-faint">·</span>
      <span className="uppercase">{role}</span>
      <span className="text-text-faint">·</span>
      <span className="tabular-nums">{confidence.toFixed(2)}</span>
      {latencyDisplay && (
        <>
          <span className="text-text-faint">·</span>
          <span className="tabular-nums">{latencyDisplay}</span>
        </>
      )}
    </span>
  );
};
