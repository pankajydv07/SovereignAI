import React, { useState } from "react";
import { ChevronUp, ChevronDown } from "lucide-react";

export interface TraceStepItem {
  stepIndex: number;
  description: string;
  tool: string;
  status: "pending" | "in_progress" | "completed" | "failed" | "interrupted";
  inputJson?: string;
  outputJson?: string;
  critiqueText?: string;
  elapsedMs?: number;
}

export interface RunTraceProps {
  steps: TraceStepItem[];
  stepCount: number;
  maxSteps: number;
  totalTokens: number;
  maxTokens: number;
}

export const RunTrace: React.FC<RunTraceProps> = ({
  steps,
  stepCount,
  maxSteps,
  totalTokens,
  maxTokens,
}) => {
  const [expandedSteps, setExpandedSteps] = useState<Record<number, boolean>>({});

  const toggleExpand = (stepIndex: number) => {
    setExpandedSteps((prev) => ({
      ...prev,
      [stepIndex]: !prev[stepIndex],
    }));
  };

  const stepPct = Math.min(100, Math.round((stepCount / maxSteps) * 100));
  const tokenPct = Math.min(100, Math.round((totalTokens / maxTokens) * 100));

  return (
    <div
      data-testid="run-trace-panel"
      className="bg-[#121821] border border-[#263241] rounded-[4px] p-4 text-[13px] text-[#E6EDF3] font-sans my-3"
    >
      {/* Budget Meter Bar */}
      <div
        data-testid="budget-meter-bar"
        className="mb-4 pb-3 border-b border-[#263241] grid grid-cols-2 gap-4 font-mono text-[12px]"
      >
        <div>
          <div className="flex justify-between mb-1">
            <span className="text-[#A0AEC0]">Steps Budget:</span>
            <span>
              {stepCount} / {maxSteps} ({stepPct}%)
            </span>
          </div>
          <div className="w-full bg-[#0B0F14] h-2 rounded-[4px] overflow-hidden">
            <div
              className="bg-[#4C8DF6] h-full transition-all duration-150"
              style={{ width: `${stepPct}%` }}
            />
          </div>
        </div>

        <div>
          <div className="flex justify-between mb-1">
            <span className="text-[#A0AEC0]">Tokens Budget:</span>
            <span>
              {totalTokens} / {maxTokens} ({tokenPct}%)
            </span>
          </div>
          <div className="w-full bg-[#0B0F14] h-2 rounded-[4px] overflow-hidden">
            <div
              className="bg-[#10B981] h-full transition-all duration-150"
              style={{ width: `${tokenPct}%` }}
            />
          </div>
        </div>
      </div>

      {/* Step Trace Rows */}
      <div className="space-y-1">
        {steps.map((step) => {
          const isExpanded = !!expandedSteps[step.stepIndex];
          return (
            <div
              key={step.stepIndex}
              data-testid={`trace-step-${step.stepIndex}`}
              className="border border-[#263241] rounded-[4px] bg-[#0B0F14] overflow-hidden"
            >
              <div
                onClick={() => toggleExpand(step.stepIndex)}
                className="h-[30px] px-3 flex items-center justify-between cursor-pointer hover:bg-[#121821] transition-colors font-mono text-[12px]"
              >
                <div className="flex items-center space-x-3">
                  <span
                    data-testid={`status-glyph-${step.stepIndex}`}
                    className={`w-2 h-2 rounded-full ${
                      step.status === "completed"
                        ? "bg-[#10B981]"
                        : step.status === "failed"
                        ? "bg-[#EF4444]"
                        : step.status === "in_progress"
                        ? "bg-[#F59E0B] animate-pulse"
                        : "bg-[#263241]"
                    }`}
                  />
                  <span className="text-[#4C8DF6]">#{step.stepIndex}</span>
                  {step.tool === "model_swap" ? (
                    <span data-testid={`model-swap-row-${step.stepIndex}`} className="text-[#F59E0B] font-bold animate-pulse">
                      waking {step.description}… {step.elapsedMs ? (step.elapsedMs / 1000).toFixed(1) : "0.0"}s
                    </span>
                  ) : (
                    <span className="text-[#E6EDF3]">{step.description}</span>
                  )}
                </div>

                <div className="flex items-center space-x-3">
                  <span className="px-2 py-0.5 bg-[#263241] text-[#E6EDF3] rounded-[4px]">
                    {step.tool}
                  </span>
                  {step.elapsedMs && (
                    <span className="text-[#A0AEC0]">{step.elapsedMs}ms</span>
                  )}
                  <span className="text-[#A0AEC0]">{isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}</span>
                </div>
              </div>

              {isExpanded && (
                <div className="p-3 border-t border-[#263241] bg-[#121821] font-mono text-[11px] space-y-2">
                  {step.inputJson && (
                    <div>
                      <div className="text-[#A0AEC0] mb-1 font-bold">Tool Input JSON:</div>
                      <pre className="p-2 bg-[#0B0F14] border border-[#263241] rounded-[4px] overflow-x-auto text-[#10B981]">
                        {step.inputJson}
                      </pre>
                    </div>
                  )}

                  {step.outputJson && (
                    <div>
                      <div className="text-[#A0AEC0] mb-1 font-bold">Tool Output JSON:</div>
                      <pre className="p-2 bg-[#0B0F14] border border-[#263241] rounded-[4px] overflow-x-auto text-[#E6EDF3]">
                        {step.outputJson}
                      </pre>
                    </div>
                  )}

                  {step.critiqueText && (
                    <div>
                      <div className="text-[#EF4444] mb-1 font-bold">
                        Critique Evaluation Verbatim:
                      </div>
                      <pre
                        data-testid={`critique-text-${step.stepIndex}`}
                        className="p-2 bg-[#0B0F14] border border-[#EF4444]/40 rounded-[4px] overflow-x-auto text-[#EF4444]"
                      >
                        {step.critiqueText}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
