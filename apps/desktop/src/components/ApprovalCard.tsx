import React from "react";

export type PermissionOption = "allow_once" | "allow_session" | "always_allow" | "deny";

export interface ApprovalCardProps {
  requestId: string;
  tool: string;
  sideEffect: string;
  resourcePattern: string;
  description: string;
  diffOrCommand?: string;
  onRespond: (requestId: string, option: PermissionOption) => void;
}

export const ApprovalCard: React.FC<ApprovalCardProps> = ({
  requestId,
  tool,
  sideEffect,
  resourcePattern,
  description,
  diffOrCommand,
  onRespond,
}) => {
  return (
    <div
      data-testid="approval-card"
      className="bg-[#121821] border-2 border-[#F59E0B] rounded-[4px] p-4 text-[13px] text-[#E6EDF3] font-sans my-3 shadow-lg"
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
        <span className="font-mono text-[11px] text-[#263241] select-all">
          ID: {requestId}
        </span>
      </div>

      <div className="mb-3 text-[13px]">{description}</div>

      {resourcePattern && (
        <div
          data-testid="pattern-scope"
          className="mb-3 p-2 bg-[#0B0F14] border border-[#263241] rounded-[4px] font-mono text-[12px] text-[#4C8DF6]"
        >
          Pattern Scope: <span className="text-[#E6EDF3]">{resourcePattern}</span>
        </div>
      )}

      {diffOrCommand && (
        <div className="mb-4">
          <div className="font-mono text-[11px] text-[#263241] mb-1 uppercase">
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
          onClick={() => onRespond(requestId, "allow_once")}
          className="px-3 py-1.5 bg-[#10B981] hover:bg-[#0D9668] text-[#0B0F14] font-mono font-semibold rounded-[4px] text-[12px]"
        >
          Allow Once
        </button>
        <button
          data-testid="allow-session-btn"
          onClick={() => onRespond(requestId, "allow_session")}
          className="px-3 py-1.5 bg-[#4C8DF6] hover:bg-[#3B72C9] text-[#0B0F14] font-mono font-semibold rounded-[4px] text-[12px]"
        >
          Allow Session
        </button>
        <button
          data-testid="always-allow-btn"
          onClick={() => onRespond(requestId, "always_allow")}
          className="px-3 py-1.5 bg-[#263241] hover:bg-[#344458] text-[#E6EDF3] font-mono font-semibold rounded-[4px] text-[12px]"
        >
          Always Allow Scope ({resourcePattern})
        </button>
        <button
          data-testid="deny-btn"
          onClick={() => onRespond(requestId, "deny")}
          className="px-3 py-1.5 bg-[#EF4444] hover:bg-[#DC2626] text-[#E6EDF3] font-mono font-semibold rounded-[4px] text-[12px]"
        >
          Deny Action
        </button>
      </div>
    </div>
  );
};
