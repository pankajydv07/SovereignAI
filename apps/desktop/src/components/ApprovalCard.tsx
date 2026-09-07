import React, { useState } from "react";

export type PermissionOption = "allow_once" | "allow_session" | "always_allow" | "deny";

export interface ApprovalCardProps {
  requestId: string;
  tool: string;
  sideEffect: string;
  resource?: string;
  resourcePattern?: string;
  description: string;
  diffOrCommand?: string;
  onRespond: (requestId: string, option: PermissionOption, chosenPattern?: string) => void;
}

export const ApprovalCard: React.FC<ApprovalCardProps> = ({
  requestId,
  tool,
  sideEffect,
  resource,
  resourcePattern,
  description,
  diffOrCommand,
  onRespond,
}) => {
  // Compute scoping options
  const exactPath = resource || "";
  const parentPattern = (() => {
    if (!exactPath || exactPath.startsWith("<") || !exactPath.includes("/")) return "**";
    const parts = exactPath.replace(/\\/g, "/").split("/");
    parts.pop();
    return parts.length > 0 ? `${parts.join("/")}/**` : "**";
  })();

  const [selectedPattern, setSelectedPattern] = useState<string>(
    resourcePattern || parentPattern
  );

  return (
    <div
      data-testid="approval-card"
      className="bg-[#121821] border-2 border-[#F59E0B] rounded-[4px] p-4 text-[13px] text-[#E6EDF3] font-sans my-3"
    >
      <div className="flex items-center justify-between border-b border-[#263241] pb-2 mb-3">
        <div className="flex items-center space-x-2 font-mono font-bold text-[#F59E0B]">
          <span className="px-2 py-0.5 bg-[#F59E0B]/20 rounded-[4px] uppercase text-[11px]">
            Approval Required
          </span>
          <span>
            {tool} ({sideEffect})
          </span>
        </div>
        <span className="font-mono text-[11px] text-[#8B949E] select-all">
          ID: {requestId.slice(0, 8)}
        </span>
      </div>

      <div className="mb-3 text-[13px]">{description}</div>

      {/* Scope Selector */}
      {exactPath && !exactPath.startsWith("<") && (
        <div className="mb-3 p-2 bg-[#0B0F14] border border-[#263241] rounded-[4px]">
          <div className="font-mono text-[11px] text-[#8B949E] uppercase mb-1.5">
            Permission Scope
          </div>
          <div className="flex flex-wrap gap-2 text-[12px] font-mono">
            <button
              type="button"
              onClick={() => setSelectedPattern(exactPath)}
              className={`px-2 py-1 rounded-[4px] border ${
                selectedPattern === exactPath
                  ? "border-[#4C8DF6] bg-[#4C8DF6]/20 text-[#4C8DF6]"
                  : "border-[#263241] bg-[#121821] text-[#8B949E]"
              }`}
            >
              Exact ({exactPath})
            </button>
            {parentPattern !== "**" && (
              <button
                type="button"
                onClick={() => setSelectedPattern(parentPattern)}
                className={`px-2 py-1 rounded-[4px] border ${
                  selectedPattern === parentPattern
                    ? "border-[#4C8DF6] bg-[#4C8DF6]/20 text-[#4C8DF6]"
                    : "border-[#263241] bg-[#121821] text-[#8B949E]"
                }`}
              >
                Parent ({parentPattern})
              </button>
            )}
            <button
              type="button"
              onClick={() => setSelectedPattern("**")}
              className={`px-2 py-1 rounded-[4px] border ${
                selectedPattern === "**"
                  ? "border-[#4C8DF6] bg-[#4C8DF6]/20 text-[#4C8DF6]"
                  : "border-[#263241] bg-[#121821] text-[#8B949E]"
              }`}
            >
              Anywhere (**)
            </button>
          </div>
        </div>
      )}

      {diffOrCommand && (
        <div className="mb-4">
          <div className="font-mono text-[11px] text-[#8B949E] mb-1 uppercase">
            Exact Content / Command Diff
          </div>
          <pre
            data-testid="diff-command-pre"
            className="p-3 bg-[#0B0F14] border border-[#263241] rounded-[4px] font-mono text-[12px] text-[#10B981] overflow-x-auto max-h-60"
          >
            {diffOrCommand}
          </pre>
        </div>
      )}

      <div className="flex flex-wrap gap-2 pt-2 border-t border-[#263241]">
        <button
          data-testid="allow-once-btn"
          onClick={() => onRespond(requestId, "allow_once", selectedPattern)}
          className="px-3 py-1.5 bg-[#10B981] hover:bg-[#0D9668] text-[#0B0F14] font-mono font-semibold rounded-[4px] text-[12px]"
        >
          Allow Once
        </button>
        <button
          data-testid="allow-session-btn"
          onClick={() => onRespond(requestId, "allow_session", selectedPattern)}
          className="px-3 py-1.5 bg-[#4C8DF6] hover:bg-[#3B72C9] text-[#0B0F14] font-mono font-semibold rounded-[4px] text-[12px]"
        >
          Allow Session
        </button>
        <button
          data-testid="always-allow-btn"
          onClick={() => onRespond(requestId, "always_allow", selectedPattern)}
          className="px-3 py-1.5 bg-[#263241] hover:bg-[#344458] text-[#E6EDF3] font-mono font-semibold rounded-[4px] text-[12px]"
        >
          Always Allow Scope ({selectedPattern})
        </button>
        <button
          data-testid="deny-btn"
          onClick={() => onRespond(requestId, "deny")}
          className="px-3 py-1.5 bg-[#EF4444] hover:bg-[#DC2626] text-[#E6EDF3] font-mono font-semibold rounded-[4px] text-[12px]"
        >
          Deny
        </button>
      </div>
    </div>
  );
};
