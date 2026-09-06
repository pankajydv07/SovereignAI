import React, { useState, useEffect, useRef } from "react";
import { Plus, MessageSquare, AlertTriangle, RefreshCw, Archive, CheckCircle2, Circle } from "lucide-react";
import { SessionInfo } from "../protocol";
import { UIState } from "../types/ui";
import { StageIndicator } from "./StageIndicator";

interface SessionListProps {
  sessions: SessionInfo[];
  activeSessionId: string | null;
  uiState: UIState;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  onCloseSession: (sessionId: string) => void;
  onRetry: () => void;
}

export const SessionList: React.FC<SessionListProps> = ({
  sessions,
  activeSessionId,
  uiState,
  onSelectSession,
  onNewSession,
  onCloseSession,
  onRetry,
}) => {
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const listRef = useRef<HTMLDivElement>(null);

  // Keyboard navigation (j/k)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (sessions.length === 0) return;

      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, sessions.length - 1));
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === "Enter" && sessions[selectedIndex]) {
        e.preventDefault();
        onSelectSession(sessions[selectedIndex].sessionId);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [sessions, selectedIndex, onSelectSession]);

  return (
    <div className="flex flex-col h-full bg-surface border-r border-border w-64 select-none">
      {/* Drawer Sub-Header */}
      <div className="h-10 px-3 border-b border-border flex items-center justify-between font-mono text-xs">
        <span className="font-semibold text-text uppercase tracking-wider text-[11px]">SESSIONS</span>
        <button
          onClick={onNewSession}
          title="New Session (⌘N)"
          className="p-1 rounded-sm bg-accent/10 border border-accent/30 text-accent hover:bg-accent/20 transition-colors cursor-pointer flex items-center gap-1"
        >
          <Plus className="w-3.5 h-3.5" />
          <span className="text-[11px] font-semibold">New</span>
        </button>
      </div>

      {/* Degraded State Banner */}
      {uiState.type === "degraded" && (
        <div className="p-3 bg-verify/10 border-b border-verify/30 text-xs font-mono text-verify space-y-2">
          <div className="flex items-center gap-1.5 font-semibold text-[11px]">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            <span>Core Unavailable</span>
          </div>
          <p className="text-[10px] leading-tight text-verify/90">{uiState.message}</p>
          <button
            onClick={onRetry}
            className="w-full py-1 bg-verify/20 hover:bg-verify/30 border border-verify/40 text-verify text-[10px] rounded-sm flex items-center justify-center gap-1 cursor-pointer transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
            {uiState.remedyLabel}
          </button>
        </div>
      )}

      {/* Body List Area */}
      <div ref={listRef} className="flex-1 overflow-y-auto p-2 space-y-1">
        {uiState.type === "loading" && (
          <div className="p-4 flex items-center justify-center">
            <StageIndicator label={uiState.stage} elapsedMs={uiState.elapsedMs} />
          </div>
        )}

        {uiState.type === "error" && (
          <div className="p-3 bg-critical/10 border border-critical/30 rounded-sm space-y-2 font-mono text-xs text-critical">
            <div className="flex items-center gap-1.5 font-semibold text-[11px]">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>Session Error</span>
            </div>
            <p className="text-[10px] text-critical/90 leading-tight">{uiState.message}</p>
            <button
              onClick={onRetry}
              className="w-full py-1 bg-critical/20 hover:bg-critical/30 border border-critical/40 text-critical text-[10px] rounded-sm flex items-center justify-center gap-1 cursor-pointer transition-colors"
            >
              <RefreshCw className="w-3 h-3" />
              {uiState.remedyLabel}
            </button>
          </div>
        )}

        {uiState.type === "empty" && (
          <div className="p-4 text-left space-y-2 border border-border border-dashed rounded-sm bg-surface-2">
            <div className="text-xs font-semibold text-text">No active sessions</div>
            <p className="text-[11px] text-text-dim leading-relaxed">
              {uiState.suggestion || "Start a new session to inspect documents."}
            </p>
            <button
              onClick={onNewSession}
              className="px-2.5 py-1 bg-accent text-white text-[11px] font-mono rounded-sm flex items-center gap-1 cursor-pointer transition-colors"
            >
              <Plus className="w-3 h-3" />
              {uiState.actionLabel || "Create New Session"}
            </button>
          </div>
        )}

        {(uiState.type === "default" || uiState.type === "degraded") &&
          sessions.map((sess, idx) => {
            const isActive = sess.sessionId === activeSessionId;
            const isKeyboardSelected = idx === selectedIndex;
            return (
              <div
                key={sess.sessionId}
                onClick={() => onSelectSession(sess.sessionId)}
                tabIndex={0}
                className={`p-2 rounded-sm border transition-all cursor-pointer focus:outline-none ${
                  isActive
                    ? "bg-surface-2 border-accent text-text"
                    : isKeyboardSelected
                    ? "bg-surface-2/60 border-border text-text ring-2 ring-accent"
                    : "bg-surface border-transparent hover:bg-surface-2 hover:border-border text-text-dim"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 min-w-0">
                    <MessageSquare className={`w-3.5 h-3.5 shrink-0 ${isActive ? "text-accent" : "text-text-dim"}`} />
                    <span className="text-xs font-semibold truncate">{sess.title}</span>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0 font-mono text-[10px]">
                    {sess.status === "active" ? (
                      <span className="flex items-center gap-1 text-sovereign">
                        <CheckCircle2 className="w-3 h-3" />
                      </span>
                    ) : (
                      <span className="text-text-faint">
                        <Circle className="w-3 h-3" />
                      </span>
                    )}

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onCloseSession(sess.sessionId);
                      }}
                      title="Close session"
                      className="p-0.5 text-text-faint hover:text-text hover:bg-surface-2 rounded transition-colors cursor-pointer"
                    >
                      <Archive className="w-3 h-3" />
                    </button>
                  </div>
                </div>
                <div className="font-mono text-[10px] text-text-faint mt-1 pl-5">
                  {new Date(sess.updatedAtMs).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </div>
              </div>
            );
          })}
      </div>
    </div>
  );
};
