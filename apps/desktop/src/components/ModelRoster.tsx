import React from "react";

export interface ModelRosterItem {
  tag: string;
  digest: string;
  parameterSize: string;
  quantizationLevel: string;
  contextLength: number;
  supportsVision: boolean;
  supportsThinking: boolean;
  supportsTools: boolean;
  family: string;
  sizeVram: string;
  sizeTotal: string;
  isResident: boolean;
}

export interface ModelRosterProps {
  models: ModelRosterItem[];
  onSelectModel?: (tag: string) => void;
}

export const ModelRoster: React.FC<ModelRosterProps> = ({ models, onSelectModel }) => {
  return (
    <div
      data-testid="model-roster-panel"
      className="bg-[#121821] border border-[#263241] rounded-[4px] p-4 text-[13px] text-[#E6EDF3] font-sans my-3"
    >
      <div className="flex items-center justify-between border-b border-[#263241] pb-2 mb-3 font-mono">
        <span className="font-semibold uppercase tracking-wider text-[#4C8DF6]">
          Installed Model Roster ({models.length})
        </span>
        <span className="text-[11px] text-[#A0AEC0]">
          Source: Local Ollama (127.0.0.1:11434)
        </span>
      </div>

      {models.length === 0 ? (
        <div
          data-testid="no-models-msg"
          className="text-[#A0AEC0] italic py-6 text-center border border-dashed border-[#263241] rounded-[4px] font-mono"
        >
          No models discovered in local Ollama repository.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse font-mono text-[12px] text-left">
            <thead>
              <tr className="border-b border-[#263241] text-[#A0AEC0] uppercase text-[11px]">
                <th className="py-2 px-3">Model Tag</th>
                <th className="py-2 px-3">Params</th>
                <th className="py-2 px-3">Quant</th>
                <th className="py-2 px-3">Max Ctx</th>
                <th className="py-2 px-3">Capabilities</th>
                <th className="py-2 px-3">VRAM / RAM</th>
                <th className="py-2 px-3">Residency</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m, idx) => (
                <tr
                  key={m.tag}
                  data-testid={`model-row-${idx}`}
                  onClick={() => onSelectModel?.(m.tag)}
                  className="border-b border-[#263241]/50 hover:bg-[#0B0F14]/60 transition-colors cursor-pointer"
                >
                  <td className="py-2.5 px-3 font-bold text-[#E6EDF3] truncate max-w-[200px]">
                    {m.tag}
                  </td>
                  <td className="py-2.5 px-3 text-[#4C8DF6]">{m.parameterSize}</td>
                  <td className="py-2.5 px-3 text-[#A0AEC0]">{m.quantizationLevel}</td>
                  <td className="py-2.5 px-3 text-[#E6EDF3]">{m.contextLength.toLocaleString()}</td>
                  <td className="py-2.5 px-3">
                    <div className="flex items-center space-x-1.5">
                      {m.supportsTools && (
                        <span
                          data-testid={`cap-tools-${m.tag}`}
                          className="px-1.5 py-0.5 bg-[#4C8DF6]/20 text-[#4C8DF6] rounded-[4px] text-[10px] uppercase font-semibold"
                        >
                          Tools
                        </span>
                      )}
                      {m.supportsThinking && (
                        <span
                          data-testid={`cap-thinking-${m.tag}`}
                          className="px-1.5 py-0.5 bg-[#F59E0B]/20 text-[#F59E0B] rounded-[4px] text-[10px] uppercase font-semibold"
                        >
                          Think
                        </span>
                      )}
                      {m.supportsVision && (
                        <span
                          data-testid={`cap-vision-${m.tag}`}
                          className="px-1.5 py-0.5 bg-[#10B981]/20 text-[#10B981] rounded-[4px] text-[10px] uppercase font-semibold"
                        >
                          Vision
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="py-2.5 px-3 text-[11px] whitespace-nowrap">
                    <span className="text-[#10B981] font-semibold">{m.sizeVram}</span>
                    <span className="text-[#A0AEC0]"> / </span>
                    <span className="text-[#A0AEC0]">{m.sizeTotal}</span>
                  </td>
                  <td className="py-2.5 px-3">
                    <span
                      data-testid={`model-residency-badge-${m.tag}`}
                      className={`px-2 py-0.5 rounded-[4px] text-[11px] uppercase font-semibold ${
                        m.isResident
                          ? "bg-[#10B981]/20 text-[#10B981] border border-[#10B981]/30"
                          : "bg-[#263241] text-[#A0AEC0]"
                      }`}
                    >
                      {m.isResident ? "Resident" : "Unloaded"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
