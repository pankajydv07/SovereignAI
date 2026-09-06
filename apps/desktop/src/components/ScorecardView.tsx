import React from "react";
import { getModelTagTint } from "./GpuAllocationBar";

export interface ScorecardModelPriors {
  modelTag: string;
  priors: Record<string, number>; // task_class -> score (0.0 to 1.0)
}

export interface ScorecardMetadata {
  gpu: string;
  date: string;
  suite: string;
}

export interface ScorecardViewProps {
  metadata?: ScorecardMetadata;
  modelsPriors: ScorecardModelPriors[];
  taskClasses?: string[];
}

const DEFAULT_CLASSES = [
  "code_generate",
  "code_debug",
  "doc_summarise",
  "doc_extract",
  "engineering_calc",
  "official_drafting",
  "vision_ocr",
  "kb_qa",
  "other",
];

export const ScorecardView: React.FC<ScorecardViewProps> = ({
  metadata = {
    gpu: "NVIDIA GeForce RTX 4090",
    date: "2026-09-06",
    suite: "eval suite v1",
  },
  modelsPriors,
  taskClasses = DEFAULT_CLASSES,
}) => {
  return (
    <div
      data-testid="scorecard-view"
      className="bg-[#121821] border border-[#263241] rounded-[4px] p-5 text-[13px] text-[#E6EDF3] font-sans my-4 space-y-4"
    >
      {/* Header Stamp */}
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-[#263241] pb-3 gap-2 font-mono">
        <div>
          <div className="text-[14px] font-bold text-[#E6EDF3] uppercase tracking-wider">
            Model Performance Scorecard
          </div>
          <div className="text-[11px] text-[#A0AEC0]">
            Empirical quality priors benchmarked across task classes
          </div>
        </div>

        <div
          data-testid="scorecard-stamp"
          className="px-3 py-1.5 bg-[#0B0F14] border border-[#10B981]/40 rounded-[4px] text-[11px] text-[#10B981] font-semibold tracking-wide"
        >
          measured on {metadata.gpu} · {metadata.date} · {metadata.suite}
        </div>
      </div>

      {/* Grouped Bars per Task Class */}
      <div className="space-y-4">
        {taskClasses.map((taskCls) => (
          <div
            key={taskCls}
            data-testid={`task-class-group-${taskCls}`}
            className="p-3 bg-[#0B0F14] border border-[#263241] rounded-[4px] space-y-2"
          >
            <div className="font-mono text-[12px] font-bold text-[#4C8DF6] uppercase tracking-wider flex justify-between">
              <span>{taskCls}</span>
              <span className="text-[11px] text-[#A0AEC0] font-normal">Target Class</span>
            </div>

            <div className="space-y-1.5">
              {modelsPriors.map((m) => {
                const score = m.priors[taskCls] ?? 0.85;
                const scorePct = Math.min(100, Math.max(0, score * 100));
                const barColor = getModelTagTint(m.modelTag);

                return (
                  <div
                    key={`${taskCls}-${m.modelTag}`}
                    data-testid={`model-bar-${taskCls}-${m.modelTag}`}
                    className="flex items-center space-x-3 font-mono text-[11px]"
                  >
                    <span className="w-[140px] text-[#E6EDF3] truncate font-medium" title={m.modelTag}>
                      {m.modelTag}
                    </span>

                    <div className="flex-1 bg-[#121821] h-4 rounded-[4px] border border-[#263241] overflow-hidden p-0.5">
                      <div
                        className="h-full rounded-[2px] transition-all duration-300"
                        style={{
                          width: `${scorePct}%`,
                          backgroundColor: barColor,
                        }}
                      />
                    </div>

                    <span className="w-[45px] text-right text-[#10B981] font-bold tabular-nums">
                      {score.toFixed(2)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
