import React from "react";

export interface RoleFulfilmentItem {
  role: string;
  satisfied: boolean;
  modelTag: string | null;
  residency: "RESIDENT" | "UNLOADED" | "MISSING" | "UNCONFIGURED";
  vramUsage: string;
  consequence: string | null;
}

export interface RoleFulfilmentPanelProps {
  fulfilment: RoleFulfilmentItem[];
  onRefresh?: () => void;
}

export const RoleFulfilmentPanel: React.FC<RoleFulfilmentPanelProps> = ({
  fulfilment,
  onRefresh,
}) => {
  const allSatisfied = fulfilment.length > 0 && fulfilment.every((f) => f.satisfied);
  const unsatisfiedItems = fulfilment.filter((f) => !f.satisfied);

  return (
    <div
      data-testid="role-fulfilment-panel"
      className="bg-[#121821] border border-[#263241] rounded-[4px] p-4 text-[13px] text-[#E6EDF3] font-sans my-3"
    >
      <div className="flex items-center justify-between border-b border-[#263241] pb-2 mb-3">
        <div className="flex items-center space-x-3">
          <span className="font-mono font-semibold uppercase tracking-wider text-[#4C8DF6]">
            Role Fulfilment Status
          </span>
          <span
            data-testid="overall-status-badge"
            className={`px-2 py-0.5 rounded-[4px] font-mono text-[11px] font-semibold uppercase ${
              allSatisfied
                ? "bg-[#10B981]/20 text-[#10B981] border border-[#10B981]/40"
                : "bg-[#EF4444]/20 text-[#EF4444] border border-[#EF4444]/40"
            }`}
          >
            {allSatisfied ? "All Roles Satisfied" : `${unsatisfiedItems.length} Unsatisfied`}
          </span>
        </div>
        {onRefresh && (
          <button
            data-testid="refresh-roles-btn"
            onClick={onRefresh}
            className="px-2.5 py-1 bg-[#263241] hover:bg-[#4C8DF6] text-[#E6EDF3] rounded-[4px] font-mono text-[11px] font-semibold transition-colors"
          >
            Refresh Roster
          </button>
        )}
      </div>

      {/* Unsatisfied Role Consequence Banners */}
      {unsatisfiedItems.length > 0 && (
        <div className="space-y-2 mb-3" data-testid="consequence-banners">
          {unsatisfiedItems.map((item) => (
            <div
              key={`consequence-${item.role}`}
              data-testid={`consequence-banner-${item.role}`}
              className="p-2.5 bg-[#EF4444]/10 border border-[#EF4444]/40 rounded-[4px] font-mono text-[12px] text-[#EF4444] flex items-start justify-between"
            >
              <div className="space-y-1">
                <div className="font-semibold uppercase tracking-wide">
                  Role Warning: {item.role}
                </div>
                <div className="text-[11px] text-[#E6EDF3]/90">{item.consequence}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Role Grid / Table */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5">
        {fulfilment.map((item) => (
          <div
            key={item.role}
            data-testid={`role-card-${item.role}`}
            className={`p-3 bg-[#0B0F14] border rounded-[4px] font-mono text-[12px] space-y-1.5 ${
              item.satisfied ? "border-[#263241]" : "border-[#EF4444]/50"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-bold text-[#E6EDF3] uppercase tracking-wide">
                {item.role}
              </span>
              <span
                data-testid={`role-residency-${item.role}`}
                className={`px-1.5 py-0.5 rounded-[4px] text-[10px] font-semibold uppercase ${
                  item.residency === "RESIDENT"
                    ? "bg-[#10B981]/20 text-[#10B981]"
                    : item.residency === "UNLOADED"
                    ? "bg-[#F59E0B]/20 text-[#F59E0B]"
                    : "bg-[#EF4444]/20 text-[#EF4444]"
                }`}
              >
                {item.residency}
              </span>
            </div>

            <div className="text-[#A0AEC0] text-[11px] truncate" title={item.modelTag || "None"}>
              Model:{" "}
              <span className="text-[#4C8DF6]">
                {item.modelTag ? item.modelTag : "Unconfigured"}
              </span>
            </div>

            <div className="text-[#A0AEC0] text-[11px] flex justify-between">
              <span>VRAM Allocation:</span>
              <span className="text-[#E6EDF3]">{item.vramUsage}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
