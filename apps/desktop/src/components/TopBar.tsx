import React from "react";
import { ShieldCheck, ChevronDown, Cpu, RefreshCw, AlertTriangle } from "lucide-react";
import { CoreState } from "../protocol";

interface TopBarProps {
  coreState?: CoreState;
  onOpenSovereignty?: () => void;
  egressCount?: number;
  isAirGapped?: boolean;
  currentUser?: {
    id: string;
    name: string;
    designation: string;
  };
  gpuUsagePercent?: number | null;
}

export const TopBar: React.FC<TopBarProps> = ({
  coreState,
  onOpenSovereignty,
  egressCount = 0,
  isAirGapped = true,
  currentUser,
  gpuUsagePercent = null,
}) => {
  const renderCoreStatusBadge = () => {
    if (!coreState) {
      return (
        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface-2 border border-border text-text-dim flex items-center gap-1">
          <Cpu className="w-3 h-3 text-text-dim" />
          STDIO CORE
        </span>
      );
    }

    switch (coreState.type) {
      case "ready":
        return (
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-sovereign/10 border border-sovereign/30 text-sovereign flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-sovereign animate-pulse" />
            CORE v{coreState.version} (ACP {coreState.protocol_version})
          </span>
        );
      case "restarting":
        return (
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-verify/10 border border-verify/30 text-verify flex items-center gap-1">
            <RefreshCw className="w-3 h-3 animate-spin text-verify" />
            CORE RESTARTING (Attempt {coreState.attempt}/5)
          </span>
        );
      case "failed":
        return (
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-critical/10 border border-critical/30 text-critical flex items-center gap-1">
            <AlertTriangle className="w-3 h-3 text-critical" />
            CORE FAILED (STOPPED)
          </span>
        );
      case "connecting":
      case "disconnected":
      default:
        return (
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface-2 border border-border text-verify flex items-center gap-1">
            <RefreshCw className="w-3 h-3 animate-spin text-verify" />
            CONNECTING...
          </span>
        );
    }
  };

  return (
    <header className="h-[44px] bg-surface border-b border-border px-3 flex items-center justify-between text-xs select-none shrink-0">
      {/* Left section: App Brand & Core Status */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="font-mono font-bold tracking-wider text-text text-sm">SWARAJ</span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface-2 border border-border text-accent">
            v0.1.0
          </span>
        </div>

        {renderCoreStatusBadge()}

        <div className="h-4 w-px bg-border" />

        <div className="flex items-center gap-1.5 text-text-dim hover:text-text cursor-pointer">
          <span>MRPL / Mangalore Refinery & Petrochemicals</span>
          <ChevronDown className="w-3.5 h-3.5" />
        </div>
      </div>

      {/* Right section: User role & Sovereignty Egress Monitor */}
      <div className="flex items-center gap-4">
        {currentUser ? (
          <div className="flex items-center gap-2 font-mono text-[11px] text-text-dim">
            <span className="w-2 h-2 rounded-full bg-accent" />
            <span>{currentUser.name}</span>
            <span className="text-text-faint">·</span>
            <span className="text-text-dim uppercase">{currentUser.designation}</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 font-mono text-[11px] text-text-dim">
            <span className="w-2 h-2 rounded-full bg-sovereign" />
            <span>LOCAL OPERATOR</span>
            <span className="text-text-faint">·</span>
            <span className="text-text-dim">ON-PREMISE SESSION</span>
          </div>
        )}

        <div className="h-4 w-px bg-border" />

        {/* Sovereignty Air-Gap & Egress Badge */}
        <button
          onClick={onOpenSovereignty}
          className="flex items-center gap-2.5 bg-surface-2 hover:bg-surface-2/80 border border-border px-2.5 py-1 rounded text-[11px] font-mono cursor-pointer transition-colors"
          title="Open Sovereignty Inspection Monitor"
        >
          <div className="flex items-center gap-1.5 text-sovereign font-medium">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>{isAirGapped ? "AIR-GAPPED" : "CONNECTED"}</span>
          </div>
          <span className="text-text-faint">|</span>
          <div className="flex items-center gap-1 text-text-dim">
            <span>EGRESS</span>
            <span
              className={`font-bold ${
                egressCount > 0 ? "text-critical animate-pulse" : "text-sovereign"
              }`}
            >
              {egressCount}
            </span>
          </div>
          {gpuUsagePercent !== null && (
            <>
              <span className="text-text-faint">|</span>
              <div className="flex items-center gap-1 text-text-dim">
                <span>GPU</span>
                <span className="text-text font-bold">{gpuUsagePercent}%</span>
              </div>
            </>
          )}
        </button>
      </div>
    </header>
  );
};

