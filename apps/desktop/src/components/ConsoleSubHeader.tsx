import React from "react";
import { Shield, MessageSquare, FileCheck, Layers, ShieldCheck, Activity, Zap } from "lucide-react";

export type ConsoleTab =
  | "chat"
  | "sovereignty"
  | "review"
  | "pid"
  | "audit"
  | "attestation";

interface ConsoleSubHeaderProps {
  activeTab: ConsoleTab;
  onSelectTab: (tab: ConsoleTab) => void;
  onKillCore?: () => void;
}

export const ConsoleSubHeader: React.FC<ConsoleSubHeaderProps> = ({
  activeTab,
  onSelectTab,
  onKillCore,
}) => {
  return (
    <div className="h-9 bg-surface border-b border-border px-4 flex items-center justify-between text-xs select-none">
      <div className="flex items-center gap-1 font-mono">
        <button
          onClick={() => onSelectTab("chat")}
          className={`px-3 py-1 rounded text-[11px] flex items-center gap-1.5 transition-colors cursor-pointer ${
            activeTab === "chat"
              ? "bg-surface-2 text-accent font-semibold border border-border"
              : "text-text-dim hover:text-text"
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5" />
          <span>STREAMING CONSOLE</span>
        </button>

        <button
          onClick={() => onSelectTab("sovereignty")}
          className={`px-3 py-1 rounded text-[11px] flex items-center gap-1.5 transition-colors cursor-pointer ${
            activeTab === "sovereignty"
              ? "bg-surface-2 text-sovereign font-semibold border border-border"
              : "text-text-dim hover:text-text"
          }`}
        >
          <Shield className="w-3.5 h-3.5 text-sovereign" />
          <span>SOVEREIGNTY MONITOR</span>
        </button>

        <button
          onClick={() => onSelectTab("review")}
          className={`px-3 py-1 rounded text-[11px] flex items-center gap-1.5 transition-colors cursor-pointer ${
            activeTab === "review"
              ? "bg-surface-2 text-[#F59E0B] font-semibold border border-border"
              : "text-text-dim hover:text-text"
          }`}
        >
          <FileCheck className="w-3.5 h-3.5 text-[#F59E0B]" />
          <span>REVIEW & APPROVE</span>
        </button>

        <button
          onClick={() => onSelectTab("pid")}
          className={`px-3 py-1 rounded text-[11px] flex items-center gap-1.5 transition-colors cursor-pointer ${
            activeTab === "pid"
              ? "bg-surface-2 text-[#06B6D4] font-semibold border border-border"
              : "text-text-dim hover:text-text"
          }`}
        >
          <Layers className="w-3.5 h-3.5 text-[#06B6D4]" />
          <span>P&ID VISION</span>
        </button>

        <button
          onClick={() => onSelectTab("audit")}
          className={`px-3 py-1 rounded text-[11px] flex items-center gap-1.5 transition-colors cursor-pointer ${
            activeTab === "audit"
              ? "bg-surface-2 text-sovereign font-semibold border border-border"
              : "text-text-dim hover:text-text"
          }`}
        >
          <ShieldCheck className="w-3.5 h-3.5 text-sovereign" />
          <span>AUDIT TRAIL</span>
        </button>

        <button
          onClick={() => onSelectTab("attestation")}
          className={`px-3 py-1 rounded text-[11px] flex items-center gap-1.5 transition-colors cursor-pointer ${
            activeTab === "attestation"
              ? "bg-surface-2 text-accent font-semibold border border-border"
              : "text-text-dim hover:text-text"
          }`}
        >
          <Activity className="w-3.5 h-3.5 text-accent" />
          <span>ATTESTATION & METRICS</span>
        </button>
      </div>

      <div className="flex items-center gap-2 font-mono text-[11px]">
        {process.env.NODE_ENV !== "production" && onKillCore && (
          <button
            onClick={onKillCore}
            className="px-2 py-0.5 rounded bg-critical/10 border border-critical/30 text-critical hover:bg-critical/20 flex items-center gap-1 transition-colors cursor-pointer"
          >
            <Zap className="w-3 h-3" />
            Simulate Crash
          </button>
        )}
      </div>
    </div>
  );
};
