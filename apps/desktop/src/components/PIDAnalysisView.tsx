import React, { useState } from "react";
import {
  Eye,
  EyeOff,
  AlertCircle,
  CheckCircle,
  AlertTriangle,
  HelpCircle,
} from "lucide-react";

export interface SymbolInventoryItem {
  className: string;
  count: number;
}

export interface ExtractedTagItem {
  id: string;
  rawTag: string;
  normalizedTag: string;
  className: string;
  confidence: number | null; // null for unreadable regions per spec
  isUnreadable: boolean;
  status: "MATCHED" | "DISCREPANCY" | "UNREADABLE";
  registerMatchName?: string;
  bbox: [number, number, number, number]; // [x0, y0, x1, y1] normalized
}

export interface PIDAnalysisViewProps {
  imagePath?: string;
  evalMeta?: string;
  symbolInventory?: Record<string, number>;
  tags?: ExtractedTagItem[];
}

export const PIDAnalysisView: React.FC<PIDAnalysisViewProps> = ({
  imagePath = "c101_crude_distillation_pid_rev4.pdf",
  evalMeta = "RF-DETR Small · Roboflow P&ID dataset",
  symbolInventory = {
    instrument_tag: 4,
    instrument_dcs: 1,
    gate_valve: 8,
    control_valve: 3,
    check_valve: 2,
    pump: 2,
    vessel: 1,
    heat_exchanger: 2,
    ball_valve: 4,
    flange: 12,
    reducer: 6,
  },
  tags = [
    {
      id: "tag-1",
      rawTag: "PT-101",
      normalizedTag: "PT-101",
      className: "instrument_tag",
      confidence: 0.98,
      isUnreadable: false,
      status: "MATCHED",
      registerMatchName: "Column Top Pressure Transmitter",
      bbox: [0.05, 0.08, 0.09, 0.14],
    },
    {
      id: "tag-2",
      rawTag: "TI 202",
      normalizedTag: "TI-202",
      className: "instrument_tag",
      confidence: 0.91,
      isUnreadable: false,
      status: "MATCHED",
      registerMatchName: "Reflux Temperature Indicator",
      bbox: [0.15, 0.20, 0.19, 0.26],
    },
    {
      id: "tag-3",
      rawTag: "FIC-204A",
      normalizedTag: "FIC-204A",
      className: "instrument_dcs",
      confidence: 0.95,
      isUnreadable: false,
      status: "MATCHED",
      registerMatchName: "Crude Feed Flow Indicator Controller",
      bbox: [0.30, 0.15, 0.35, 0.22],
    },
    {
      id: "tag-4",
      rawTag: "PI-108",
      normalizedTag: "PI-108",
      className: "instrument_tag",
      confidence: 0.85,
      isUnreadable: false,
      status: "DISCREPANCY",
      registerMatchName: undefined, // Missing in equipment register!
      bbox: [0.55, 0.40, 0.60, 0.48],
    },
    {
      id: "tag-5",
      rawTag: "unreadable",
      normalizedTag: "[UNREADABLE REGION]",
      className: "instrument_tag",
      confidence: null, // null for unreadable per spec!
      isUnreadable: true,
      status: "UNREADABLE",
      registerMatchName: undefined,
      bbox: [0.72, 0.65, 0.77, 0.72],
    },
  ],
}) => {
  const [showOverlay, setShowOverlay] = useState<boolean>(true);
  const [selectedTagId, setSelectedTagId] = useState<string | null>("tag-4");

  const totalSymbols = Object.values(symbolInventory).reduce((a, b) => a + b, 0);
  const discrepancyCount = tags.filter((t) => t.status === "DISCREPANCY").length;
  const unreadableCount = tags.filter((t) => t.isUnreadable).length;

  return (
    <div
      data-testid="pid-analysis-view"
      className="flex flex-col h-full w-full bg-[#0B0F14] text-[#E6EDF3] font-sans overflow-hidden select-none"
    >
      {/* Top Console Navigation Sub-Header */}
      <div className="h-11 bg-[#121821] border-b border-[#263241] px-4 flex items-center justify-between text-[12px] font-mono">
        <div className="flex items-center gap-3">
          <span className="text-[#9AA7B4] font-semibold">P&ID VISION ANALYSIS</span>
          <span className="text-[#263241]">│</span>
          <span className="text-[#E6EDF3] font-semibold">{imagePath}</span>
          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-[#1A222E] border border-[#263241] text-[#06B6D4]">
            {evalMeta}
          </span>
        </div>

        <div className="flex items-center gap-4">
          <button
            data-testid="toggle-overlay-btn"
            onClick={() => setShowOverlay(!showOverlay)}
            className={`px-3 py-1 rounded text-[11px] font-mono font-semibold border flex items-center gap-1.5 cursor-pointer transition-colors ${
              showOverlay
                ? "bg-[#06B6D4]/20 border-[#06B6D4] text-[#06B6D4]"
                : "bg-[#1A222E] border-[#263241] text-[#9AA7B4] hover:text-[#E6EDF3]"
            }`}
          >
            {showOverlay ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span>{showOverlay ? "Annotated Overlay ON" : "Annotated Overlay OFF"}</span>
          </button>
        </div>
      </div>

      {/* Main 50/50 Viewport */}
      <div className="flex flex-1 h-full w-full overflow-hidden">
        {/* Left Pane (50%): P&ID Drawing Canvas with Bounding Box Overlay */}
        <div className="w-1/2 h-full bg-[#0B0F14] p-4 flex flex-col items-center justify-center overflow-hidden border-r border-[#263241]">
          <div
            data-testid="pid-drawing-canvas"
            className="relative w-full h-full bg-[#121821] border border-[#263241] rounded-[4px] flex items-center justify-center overflow-hidden"
          >
            {/* Simulated P&ID Blueprint Background */}
            <div className="absolute inset-0 opacity-20 bg-[radial-gradient(#263241_1px,transparent_1px)] [background-size:16px_16px]" />
            <div className="text-[14px] font-mono text-[#9AA7B4] select-none text-center">
              [P&ID BLUEPRINT DRAWING CANVAS: {imagePath}]
              <br />
              <span className="text-[11px] text-[#6B7A8A]">A0 Format · 7000×5000 px · Tiled 1024×1024 (20% overlap)</span>
            </div>

            {/* Bounding Box Annotations Overlay */}
            {showOverlay &&
              tags.map((t) => {
                const [x0, y0, x1, y1] = t.bbox;
                const left = `${x0 * 100}%`;
                const top = `${y0 * 100}%`;
                const width = `${(x1 - x0) * 100}%`;
                const height = `${(y1 - y0) * 100}%`;
                const isSelected = selectedTagId === t.id;

                const borderColor =
                  t.status === "UNREADABLE"
                    ? "#EF4444"
                    : t.status === "DISCREPANCY"
                    ? "#F59E0B"
                    : t.className === "instrument_dcs"
                    ? "#06B6D4"
                    : "#10B981";

                return (
                  <div
                    key={t.id}
                    onClick={() => setSelectedTagId(t.id)}
                    style={{
                      position: "absolute",
                      left,
                      top,
                      width,
                      height,
                      borderColor,
                    }}
                    className={`border-2 rounded-sm cursor-pointer transition-all ${
                      isSelected ? "ring-2 ring-white shadow-lg z-20 scale-105" : "opacity-80 hover:opacity-100 z-10"
                    }`}
                  >
                    <div
                      style={{ backgroundColor: borderColor }}
                      className="absolute -top-5 left-0 px-1.5 py-0.5 text-[10px] font-mono font-bold text-[#0B0F14] rounded-t whitespace-nowrap shadow"
                    >
                      {t.normalizedTag} {t.confidence !== null ? `(${t.confidence.toFixed(2)})` : "(unreadable)"}
                    </div>
                  </div>
                );
              })}
          </div>
        </div>

        {/* Right Pane (50%): Evidence Panel (Honest Disclaimer, Inventory, Tag List, Reconciliation) */}
        <div className="w-1/2 h-full bg-[#0B0F14] flex flex-col overflow-hidden">
          {/* Honest UI Disclaimer Banner (Mandatory per Spec) */}
          <div
            data-testid="honest-disclaimer-banner"
            className="p-3 bg-[#1A222E] border-b border-[#263241] flex items-start gap-2.5 text-[12px] font-sans"
          >
            <AlertCircle className="w-4 h-4 text-[#4C8DF6] flex-shrink-0 mt-0.5" />
            <div>
              <span className="font-mono font-bold text-[#4C8DF6] uppercase text-[11px] block mb-0.5">
                HONEST UI BOUNDARY STATEMENT
              </span>
              <span className="text-[#9AA7B4] leading-relaxed">
                Note: P&ID analysis performs symbol detection and tag extraction only. It does NOT reconstruct drawing topology, trace pipe lines, or validate control-loop logic.
              </span>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-6">
            {/* Section 1: Symbol Inventory Table */}
            <div>
              <div className="font-mono text-[12px] font-bold text-[#E6EDF3] mb-2 uppercase flex justify-between">
                <span>1. Symbol Inventory ({totalSymbols} detected)</span>
                <span className="text-[#9AA7B4] text-[11px] font-normal">11 Roboflow Classes</span>
              </div>

              <div className="bg-[#121821] border border-[#263241] rounded overflow-hidden">
                <table className="w-full text-left font-mono text-[11px]">
                  <thead>
                    <tr className="bg-[#1A222E] text-[#9AA7B4] border-b border-[#263241]">
                      <th className="p-2">SYMBOL CLASS</th>
                      <th className="p-2 text-right">COUNT</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#263241]">
                    {Object.entries(symbolInventory).map(([cls, cnt]) => (
                      <tr key={cls} className="hover:bg-[#1A222E]/50">
                        <td className="p-2 text-[#E6EDF3]">{cls}</td>
                        <td className="p-2 text-right font-bold text-[#4C8DF6]">{cnt}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Section 2: Equipment Register Reconciliation Table */}
            <div>
              <div className="font-mono text-[12px] font-bold text-[#E6EDF3] mb-2 uppercase flex justify-between">
                <span>2. Master Register Reconciliation</span>
                <span className="text-[#F59E0B] text-[11px] font-bold">
                  {discrepancyCount} discrepancy · {unreadableCount} unreadable
                </span>
              </div>

              <div className="space-y-2">
                {tags.map((tag) => (
                  <div
                    key={tag.id}
                    onClick={() => setSelectedTagId(tag.id)}
                    className={`p-3 bg-[#121821] border rounded-[4px] cursor-pointer transition-colors ${
                      selectedTagId === tag.id ? "border-[#4C8DF6] bg-[#1A222E]" : "border-[#263241]"
                    }`}
                  >
                    <div className="flex items-center justify-between font-mono text-[12px] mb-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-[#E6EDF3] select-all">{tag.normalizedTag}</span>
                        <span className="text-[11px] text-[#9AA7B4]">({tag.className})</span>
                      </div>

                      {tag.status === "MATCHED" ? (
                        <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-[#10B981]/20 text-[#10B981] flex items-center gap-1">
                          <CheckCircle className="w-3 h-3" /> MATCHED
                        </span>
                      ) : tag.status === "DISCREPANCY" ? (
                        <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-[#F59E0B]/20 text-[#F59E0B] flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" /> DISCREPANCY
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-[#EF4444]/20 text-[#EF4444] flex items-center gap-1">
                          <HelpCircle className="w-3 h-3" /> UNREADABLE
                        </span>
                      )}
                    </div>

                    <div className="flex items-center justify-between text-[11px] font-mono text-[#9AA7B4]">
                      <div>
                        {tag.registerMatchName ? (
                          <span className="text-[#10B981]">Reg: {tag.registerMatchName}</span>
                        ) : tag.isUnreadable ? (
                          <span className="text-[#EF4444]">OCR crop unreadable · requires human review</span>
                        ) : (
                          <span className="text-[#F59E0B]">Missing from Master Equipment Register (sessions.db)</span>
                        )}
                      </div>

                      <div>
                        <span>conf: </span>
                        <span className="font-bold text-[#E6EDF3]">
                          {tag.confidence !== null ? tag.confidence.toFixed(2) : "null"}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
