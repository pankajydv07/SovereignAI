import React from "react";

export interface PolicyRuleItem {
  projectId: string;
  tool: string;
  resourcePattern: string;
  choice: "always_allow" | "allow_session" | "deny";
  createdAtMs: number;
}

export interface PolicySettingsViewProps {
  projectId: string;
  rules: PolicyRuleItem[];
  onRevokeRule: (tool: string, resourcePattern: string) => void;
}

export const PolicySettingsView: React.FC<PolicySettingsViewProps> = ({
  projectId,
  rules,
  onRevokeRule,
}) => {
  return (
    <div
      data-testid="policy-settings-panel"
      className="bg-[#121821] border border-[#263241] rounded-[4px] p-4 text-[13px] text-[#E6EDF3] font-sans my-3"
    >
      <div className="flex items-center justify-between border-b border-[#263241] pb-2 mb-3 font-mono">
        <span className="font-semibold uppercase tracking-wider text-[#4C8DF6]">
          Project Policy Rules ({rules.length})
        </span>
        <span className="text-[11px] text-[#A0AEC0]">Project: {projectId}</span>
      </div>

      {rules.length === 0 ? (
        <div
          data-testid="no-rules-msg"
          className="text-[#A0AEC0] italic py-4 text-center border border-dashed border-[#263241] rounded-[4px]"
        >
          No persisted policy rules for this project.
        </div>
      ) : (
        <div className="space-y-2">
          {rules.map((rule, idx) => (
            <div
              key={`${rule.tool}-${rule.resourcePattern}-${idx}`}
              data-testid={`policy-rule-row-${idx}`}
              className="flex items-center justify-between p-2.5 bg-[#0B0F14] border border-[#263241] rounded-[4px] font-mono text-[12px]"
            >
              <div className="flex items-center space-x-3">
                <span className="px-2 py-0.5 bg-[#263241] text-[#E6EDF3] rounded-[4px]">
                  {rule.tool}
                </span>
                <span className="text-[#4C8DF6] font-medium">
                  {rule.resourcePattern}
                </span>
              </div>

              <div className="flex items-center space-x-3">
                <span
                  className={`px-2 py-0.5 rounded-[4px] uppercase text-[11px] font-semibold ${
                    rule.choice === "always_allow"
                      ? "bg-[#10B981]/20 text-[#10B981]"
                      : rule.choice === "allow_session"
                      ? "bg-[#4C8DF6]/20 text-[#4C8DF6]"
                      : "bg-[#EF4444]/20 text-[#EF4444]"
                  }`}
                >
                  {rule.choice}
                </span>
                <button
                  data-testid={`revoke-btn-${idx}`}
                  onClick={() => onRevokeRule(rule.tool, rule.resourcePattern)}
                  className="px-2.5 py-1 bg-[#EF4444]/10 hover:bg-[#EF4444] hover:text-[#0B0F14] text-[#EF4444] border border-[#EF4444] rounded-[4px] text-[11px] font-semibold transition-colors"
                >
                  Revoke
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
