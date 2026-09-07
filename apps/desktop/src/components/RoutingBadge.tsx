import React, { useState } from "react";
import { X } from "lucide-react";
import { getModelTagTint } from "./GpuAllocationBar";

export interface CandidateScoreItem {
  modelTag: string;
  qualityPrior: number;
  vramFit: number;
  latencyScore: number;
  swapPenalty: number;
  totalScore: number;
  isWinner: boolean;
  rejectionReason?: string | null;
}

export interface RoutingDecisionPayload {
  taskClass: string;
  selectedModelTag: string;
  fallbackModelTag: string;
  confidence: number;
  routingLatencyMs: number;
  isManualOverride: boolean;
  degradedReason?: string | null;
  featureVector?: {
    hasImage?: boolean;
    codeFences?: number;
    estimatedTokens?: number;
    keywordHits?: Record<string, number>;
  };
  candidates?: CandidateScoreItem[];
}

export interface RoutingBadgeProps {
  role: string;
  model: string;
  confidence?: number;
  latencyMs?: number;
  latencySeconds?: number;
  isManualOverride?: boolean;
  decision?: RoutingDecisionPayload;
  className?: string;
}

export const RoutingBadge: React.FC<RoutingBadgeProps> = ({
  role,
  model,
  confidence,
  latencyMs,
  latencySeconds,
  isManualOverride = false,
  decision,
  className = "",
}) => {
  const [showPopover, setShowPopover] = useState(false);

  const dotColor = getModelTagTint(model);
  const effectiveOverride = isManualOverride || (decision ? decision.isManualOverride : false);
  const effectiveConfidence = decision ? decision.confidence : confidence ?? null;
  const effectiveLatency: number | null = decision
    ? decision.routingLatencyMs
    : latencyMs !== undefined
    ? latencyMs
    : latencySeconds !== undefined
    ? Math.round(latencySeconds * 1000)
    : null;

  const candidates = decision?.candidates ?? null;
  const features = decision?.featureVector ?? null;

  return (
    <div className="relative inline-block">
      <button
        data-testid="routing-badge-button"
        onClick={() => setShowPopover(!showPopover)}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[4px] border border-[#263241] text-[11px] font-mono bg-[#0B0F14] hover:bg-[#121821] text-[#E6EDF3] transition-colors cursor-pointer ${className}`}
      >
        <span
          data-testid="routing-dot"
          className="w-2 h-2 rounded-full"
          style={{ backgroundColor: dotColor }}
        />
        <span className="font-bold text-[#E6EDF3]">{model}</span>
        <span className="text-[#A0AEC0]">·</span>
        <span className="text-[#4C8DF6] uppercase font-semibold">{role}</span>
        <span className="text-[#A0AEC0]">·</span>

        {effectiveOverride ? (
          <span
            data-testid="manual-override-badge"
            className="px-1.5 py-0.5 bg-[#F59E0B]/20 text-[#F59E0B] rounded-[4px] text-[10px] font-bold uppercase border border-[#F59E0B]/40"
          >
            MANUAL OVERRIDE
          </span>
        ) : effectiveConfidence !== null ? (
          <span data-testid="confidence-val" className="tabular-nums text-[#10B981] font-semibold">
            {effectiveConfidence.toFixed(2)}
          </span>
        ) : null}

        {effectiveLatency !== null && (
          <>
            <span className="text-[#A0AEC0]">·</span>
            <span className="tabular-nums text-[#A0AEC0]">{effectiveLatency}ms</span>
          </>
        )}
      </button>

      {/* 420px Routing Decision Popover */}
      {showPopover && (
        <div
          data-testid="routing-popover"
          className="absolute right-0 top-full mt-2 w-[420px] bg-[#121821] border border-[#263241] shadow-2xl rounded-[4px] p-4 text-[12px] font-mono text-[#E6EDF3] z-50 space-y-3"
        >
          {/* Popover Header */}
          <div className="flex items-center justify-between border-b border-[#263241] pb-2">
            <span className="font-bold uppercase tracking-wide text-[#4C8DF6]">
              Routing Decision Matrix
            </span>
            <button
              onClick={() => setShowPopover(false)}
              className="text-[#A0AEC0] hover:text-[#E6EDF3] px-1 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Feature Vector Summary — only when decision data is present */}
          {features ? (
            <div data-testid="feature-vector-box" className="p-2.5 bg-[#0B0F14] border border-[#263241] rounded-[4px] space-y-1 text-[11px]">
              <div className="text-[#A0AEC0] font-bold uppercase tracking-wider text-[10px] mb-1">
                Stage 0 Feature Vector:
              </div>
              <div className="grid grid-cols-2 gap-2 text-[#E6EDF3]">
                <div>Image Attached: <span className="text-[#4C8DF6]">{features.hasImage ? "Yes" : "No"}</span></div>
                <div>Code Fences: <span className="text-[#4C8DF6]">{features.codeFences || 0}</span></div>
                <div>Estimated Tokens: <span className="text-[#4C8DF6]">{features.estimatedTokens || 0}</span></div>
                <div>Task Class: <span className="text-[#10B981] font-semibold">{decision?.taskClass || role}</span></div>
              </div>
            </div>
          ) : (
            <div className="p-2.5 bg-[#0B0F14] border border-[#263241] rounded-[4px] text-[11px] text-[#6B7A8A] font-mono">
              No routing decision data available for this message.
            </div>
          )}

          {/* Candidate Evaluation Table — only when decision data is present */}
          {candidates && candidates.length > 0 && (
            <div>
              <div className="text-[#A0AEC0] font-bold uppercase tracking-wider text-[10px] mb-1.5">
                Candidate Evaluation Scores:
              </div>
              <div className="space-y-2">
                {candidates.map((cand, idx) => (
                  <div
                    key={`cand-${cand.modelTag}-${idx}`}
                    data-testid={`candidate-row-${idx}`}
                    className={`p-2.5 bg-[#0B0F14] rounded-[4px] border space-y-1 text-[11px] ${
                      cand.isWinner
                        ? "border-l-[3px] border-l-[#10B981] border-[#10B981]/40"
                        : "border-[#263241]"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-[#E6EDF3]">{cand.modelTag}</span>
                      {cand.isWinner ? (
                        <span data-testid={`winner-tag-${cand.modelTag}`} className="px-1.5 py-0.5 bg-[#10B981]/20 text-[#10B981] rounded-[4px] text-[10px] font-bold uppercase">
                          WINNER
                        </span>
                      ) : (
                        <span data-testid={`rejection-reason-${cand.modelTag}`} className="text-[#EF4444] text-[10px] italic">
                          {cand.rejectionReason || "lower total score"}
                        </span>
                      )}
                    </div>

                    <div className="grid grid-cols-5 gap-1 text-[10px] text-[#A0AEC0] pt-1 border-t border-[#263241]/40">
                      <div>Q.Prior: <span className="text-[#E6EDF3]">{cand.qualityPrior.toFixed(2)}</span></div>
                      <div>VRAM: <span className="text-[#E6EDF3]">{cand.vramFit.toFixed(2)}</span></div>
                      <div>Latency: <span className="text-[#E6EDF3]">{cand.latencyScore.toFixed(2)}</span></div>
                      <div>SwapPen: <span className="text-[#E6EDF3]">{cand.swapPenalty.toFixed(2)}</span></div>
                      <div className="font-bold text-[#4C8DF6]">Total: {cand.totalScore.toFixed(2)}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
