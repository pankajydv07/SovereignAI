import React from "react";

export interface PlanStepItem {
  stepIndex: number;
  description: string;
  tool: string;
  sideEffect: "read" | "write" | "exec";
  requiresApproval: boolean;
  idempotent?: boolean;
  dependencies?: number[];
}

export interface PlanCardProps {
  steps: PlanStepItem[];
  onRunPlan: () => void;
  onEditPlan?: (steps: PlanStepItem[]) => void;
  onCancelPlan: () => void;
  dependencyWarnings?: string[];
}

export const PlanCard: React.FC<PlanCardProps> = ({
  steps,
  onRunPlan,
  onCancelPlan,
  dependencyWarnings = [],
}) => {
  return (
    <div
      data-testid="plan-card"
      className="bg-[#121821] border border-[#263241] rounded-[4px] p-4 text-[13px] text-[#E6EDF3] font-sans my-3"
    >
      <div className="flex items-center justify-between border-b border-[#263241] pb-2 mb-3">
        <span className="font-mono font-semibold uppercase tracking-wider text-[#4C8DF6]">
          Execution Plan ({steps.length} steps)
        </span>
        <div className="flex space-x-2">
          <button
            data-testid="run-plan-btn"
            onClick={onRunPlan}
            className="px-3 py-1 bg-[#10B981] hover:bg-[#0D9668] text-[#0B0F14] font-mono font-medium rounded-[4px] text-[12px]"
          >
            Run Plan
          </button>
          <button
            data-testid="cancel-plan-btn"
            onClick={onCancelPlan}
            className="px-3 py-1 bg-[#263241] hover:bg-[#344458] text-[#E6EDF3] font-mono rounded-[4px] text-[12px]"
          >
            Cancel
          </button>
        </div>
      </div>

      {dependencyWarnings.length > 0 && (
        <div
          data-testid="dependency-warning"
          className="mb-3 p-2 bg-[#EF4444]/10 border border-[#EF4444] rounded-[4px] text-[#EF4444] font-mono text-[12px]"
        >
          {dependencyWarnings.map((w, idx) => (
            <div key={idx}>Warning: {w}</div>
          ))}
        </div>
      )}

      <div className="space-y-2">
        {steps.map((step) => (
          <div
            key={step.stepIndex}
            className="flex items-center justify-between p-2 bg-[#0B0F14] border border-[#263241] rounded-[4px]"
          >
            <div className="flex items-center space-x-3">
              <span className="font-mono text-[#4C8DF6] font-bold">
                #{step.stepIndex}
              </span>
              <span>{step.description}</span>
            </div>
            <div className="flex items-center space-x-2 font-mono text-[11px]">
              <span className="px-2 py-0.5 bg-[#263241] text-[#E6EDF3] rounded-[4px]">
                {step.tool}
              </span>
              <span
                className={`px-2 py-0.5 rounded-[4px] uppercase ${
                  step.sideEffect === "read"
                    ? "bg-[#10B981]/20 text-[#10B981]"
                    : step.sideEffect === "write"
                    ? "bg-[#F59E0B]/20 text-[#F59E0B]"
                    : "bg-[#EF4444]/20 text-[#EF4444]"
                }`}
              >
                {step.sideEffect}
              </span>
              {step.requiresApproval && (
                <span className="px-2 py-0.5 bg-[#F59E0B] text-[#0B0F14] font-bold rounded-[4px]">
                  ASK
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
