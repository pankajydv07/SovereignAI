import React from "react";

export interface LoadedModelItem {
  modelTag: string;
  sizeVramBytes: number;
  role?: string;
}

export interface UnloadedModelItem {
  modelTag: string;
  role?: string;
}

export interface GpuAllocationBarProps {
  loadedModels: LoadedModelItem[];
  unloadedModels: UnloadedModelItem[];
  totalVramBytes?: number; // Default: 24 GB
}

export const getModelTagTint = (modelTag: string): string => {
  const tag = modelTag.toLowerCase();
  if (tag.includes("coder")) return "#8B5CF6"; // coder tint
  if (tag.includes("vl") || tag.includes("vision")) return "#06B6D4"; // vision tint
  if (tag.includes("ocr")) return "#14B8A6"; // ocr tint
  if (tag.includes("qwen3") || tag.includes("planner")) return "#6366F1"; // planner tint
  if (tag.includes("bge") || tag.includes("embed")) return "#10B981"; // classifier/embedder tint
  if (tag.includes("write")) return "#F59E0B"; // writer tint
  return "#4C8DF6"; // default accent tint
};

export const GpuAllocationBar: React.FC<GpuAllocationBarProps> = ({
  loadedModels,
  unloadedModels,
  totalVramBytes = 24 * 1024 * 1024 * 1024,
}) => {
  const totalVramGb = (totalVramBytes / (1024 * 1024 * 1024)).toFixed(1);
  const usedVramBytes = loadedModels.reduce((acc, m) => acc + m.sizeVramBytes, 0);
  const usedVramGb = (usedVramBytes / (1024 * 1024 * 1024)).toFixed(1);
  const usedPct = Math.min(100, (usedVramBytes / totalVramBytes) * 100);

  return (
    <div
      data-testid="gpu-allocation-bar-container"
      className="bg-[#121821] border border-[#263241] rounded-[4px] p-4 text-[13px] text-[#E6EDF3] font-sans my-3 space-y-3"
    >
      {/* Header */}
      <div className="flex items-center justify-between font-mono text-[12px] border-b border-[#263241] pb-2">
        <span className="font-semibold uppercase tracking-wider text-[#4C8DF6]">
          GPU VRAM Allocation
        </span>
        <span data-testid="vram-summary-text" className="text-[#A0AEC0]">
          {usedVramGb} GB / {totalVramGb} GB ({usedPct.toFixed(1)}%)
        </span>
      </div>

      {/* 28px Stacked VRAM Allocation Bar */}
      <div
        data-testid="gpu-stacked-bar"
        className="w-full h-[28px] bg-[#0B0F14] border border-[#263241] rounded-[4px] flex overflow-hidden p-0.5 relative"
      >
        {loadedModels.map((m) => {
          const segPct = (m.sizeVramBytes / totalVramBytes) * 100;
          const bgTint = getModelTagTint(m.modelTag);
          const vramMb = (m.sizeVramBytes / (1024 * 1024)).toFixed(0);

          return (
            <div
              key={`resident-${m.modelTag}`}
              data-testid={`vram-segment-${m.modelTag}`}
              className="h-full flex items-center justify-center font-mono text-[11px] font-bold text-[#0B0F14] transition-all duration-400 motion-reduce:transition-none px-1 overflow-hidden"
              style={{
                width: `${segPct}%`,
                backgroundColor: bgTint,
              }}
              title={`${m.modelTag}: ${vramMb} MB VRAM`}
            >
              <span className="truncate">{m.modelTag}</span>
            </div>
          );
        })}

        {/* Free VRAM Segment */}
        {usedPct < 100 && (
          <div
            data-testid="vram-segment-free"
            className="h-full flex items-center justify-center font-mono text-[11px] text-[#A0AEC0] border border-dashed border-[#263241] transition-all duration-400 motion-reduce:transition-none"
            style={{ width: `${100 - usedPct}%` }}
          >
            <span className="truncate">Free VRAM</span>
          </div>
        )}
      </div>

      {/* Unloaded Configured Models Chip Row */}
      {unloadedModels.length > 0 && (
        <div data-testid="unloaded-models-row" className="flex items-center flex-wrap gap-2 pt-1 font-mono text-[11px]">
          <span className="text-[#A0AEC0]">Configured Unloaded:</span>
          {unloadedModels.map((um) => (
            <span
              key={`unloaded-${um.modelTag}`}
              data-testid={`unloaded-chip-${um.modelTag}`}
              className="px-2 py-0.5 bg-[#0B0F14] border border-[#263241] text-[#A0AEC0] rounded-[4px] flex items-center space-x-1.5"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-[#263241]" />
              <span>{um.modelTag} — not loaded</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
};
