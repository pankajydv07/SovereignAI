import React, { useEffect, useState } from "react";
import { TopBar } from "./components/TopBar";
import { LeftRail } from "./components/LeftRail";
import { ConversationPane } from "./components/ConversationPane";
import { TerminalPane } from "./components/TerminalPane";
import { SovereigntyScreen, SovereigntyStatus } from "./components/SovereigntyScreen";
import { CoreState } from "./protocol";
import { Shield, Zap, RefreshCw, Terminal, CheckCircle2, AlertOctagon, MessageSquare, Activity } from "lucide-react";

export const App: React.FC = () => {
  const [coreState, setCoreState] = useState<CoreState>({ type: "connecting" });
  const [activeTab, setActiveTab] = useState<"chat" | "diagnostics" | "sovereignty">("chat");
  const [egressCount, setEgressCount] = useState<number>(0);
  const [isAirGapped, setIsAirGapped] = useState<boolean>(true);

  useEffect(() => {
    // Check if running inside Tauri context
    const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

    if (!isTauri) {
      // Browser fallback demo state
      setCoreState({
        type: "ready",
        version: "0.1.0",
        protocol_version: "2024-11-05",
      });
      return;
    }

    let unlistenFn: (() => void) | undefined;
    let unlistenSov: (() => void) | undefined;

    const setupCoreConnection = async () => {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        const { listen } = await import("@tauri-apps/api/event");

        // Query initial state
        const initialState = await invoke<CoreState>("get_core_status");
        setCoreState(initialState);

        const sovStatus = await invoke<SovereigntyStatus>("get_sovereignty_status");
        setEgressCount(sovStatus.egress_count);
        setIsAirGapped(!sovStatus.active_link);

        // Listen for core state changes
        unlistenFn = await listen<CoreState>("core-status-changed", (event) => {
          setCoreState(event.payload);
        });

        unlistenSov = await listen<SovereigntyStatus>("sovereignty-status-changed", (event) => {
          setEgressCount(event.payload.egress_count);
          setIsAirGapped(!event.payload.active_link);
        });
      } catch (err) {
        console.error("Failed to connect to Tauri core supervisor:", err);
      }
    };

    setupCoreConnection();

    return () => {
      if (unlistenFn) unlistenFn();
      if (unlistenSov) unlistenSov();
    };
  }, []);

  const handleKillCore = async () => {
    try {
      const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
      if (isTauri) {
        const { invoke } = await import("@tauri-apps/api/core");
        await invoke("kill_core_process");
      } else {
        // Mock restart in web demo mode
        setCoreState({ type: "restarting", attempt: 1 });
        setTimeout(() => {
          setCoreState({
            type: "ready",
            version: "0.1.0",
            protocol_version: "2024-11-05",
          });
        }, 1500);
      }
    } catch (err) {
      console.error("Failed to kill core process:", err);
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-bg text-text">
      {/* 44px Top Navigation & Sovereignty Bar */}
      <TopBar
        coreState={coreState}
        onOpenSovereignty={() => setActiveTab("sovereignty")}
        egressCount={egressCount}
        isAirGapped={isAirGapped}
      />

      {/* Main Container */}
      <div className="flex flex-1 overflow-hidden">
        {/* 56px Left Rail */}
        <LeftRail />

        {/* Content Viewport */}
        <main className="flex-1 flex flex-col bg-bg overflow-hidden">
          {/* Console Sub-Header / View Selector */}
          <div className="h-9 bg-surface border-b border-border px-4 flex items-center justify-between text-xs select-none">
            <div className="flex items-center gap-1 font-mono">
              <button
                onClick={() => setActiveTab("chat")}
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
                onClick={() => setActiveTab("sovereignty")}
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
                onClick={() => setActiveTab("diagnostics")}
                className={`px-3 py-1 rounded text-[11px] flex items-center gap-1.5 transition-colors cursor-pointer ${
                  activeTab === "diagnostics"
                    ? "bg-surface-2 text-accent font-semibold border border-border"
                    : "text-text-dim hover:text-text"
                }`}
              >
                <Activity className="w-3.5 h-3.5" />
                <span>SUPERVISOR DIAGNOSTICS</span>
              </button>
            </div>

            <div className="flex items-center gap-2 font-mono text-[11px]">
              {process.env.NODE_ENV !== "production" && (
                <button
                  onClick={handleKillCore}
                  className="px-2 py-0.5 rounded bg-critical/10 border border-critical/30 text-critical hover:bg-critical/20 flex items-center gap-1 transition-colors cursor-pointer"
                >
                  <Zap className="w-3 h-3" />
                  Simulate Core Crash
                </button>
              )}
            </div>
          </div>

          {activeTab === "chat" && (
            <div className="flex-1 flex flex-col overflow-hidden">
              <div className="flex-1 overflow-hidden flex flex-col">
                <ConversationPane />
              </div>
              <TerminalPane />
            </div>
          )}

          {activeTab === "sovereignty" && <SovereigntyScreen />}

          {activeTab === "diagnostics" && (
            <div className="flex-1 flex flex-col overflow-hidden">
              <div className="flex-1 flex flex-col items-center justify-center p-6 text-center bg-bg overflow-y-auto">
                <div className="max-w-xl w-full p-6 bg-surface border border-border rounded text-left space-y-4 shadow-sm">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Shield className="w-4 h-4 text-sovereign" />
                      <span className="font-mono text-xs font-semibold text-accent">P0.3 — STREAMING CHAT THROUGH CORE</span>
                    </div>
                    <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-sovereign/10 text-sovereign border border-sovereign/20">
                      NO LISTENING SOCKET
                    </span>
                  </div>

                  <h1 className="text-sm font-semibold text-text">Rust ↔ Python Stdio JSON-RPC Supervisor</h1>

                  <p className="text-xs text-text-dim leading-relaxed">
                    Rust supervises the Python Agent Core child process over piped <code className="text-accent">stdin/stdout/stderr</code>.
                    Chat requests stream through Ollama via stdio JSON-RPC <code className="text-accent">chat/stream</code>.
                  </p>

                  {/* Core Status Card */}
                  <div className="p-3 bg-surface-2 border border-border rounded font-mono text-xs space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-text-dim">Sidecar State:</span>
                      <span className="text-text font-bold">
                        {coreState.type === "ready" && (
                          <span className="text-sovereign flex items-center gap-1">
                            <CheckCircle2 className="w-3.5 h-3.5" /> READY (v{coreState.version} / ACP {coreState.protocol_version})
                          </span>
                        )}
                        {coreState.type === "restarting" && (
                          <span className="text-verify flex items-center gap-1">
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" /> RESTARTING (Attempt {coreState.attempt}/5)
                          </span>
                        )}
                        {coreState.type === "connecting" && (
                          <span className="text-verify flex items-center gap-1">
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" /> CONNECTING
                          </span>
                        )}
                        {coreState.type === "failed" && (
                          <span className="text-critical flex items-center gap-1">
                            <AlertOctagon className="w-3.5 h-3.5" /> FAILED
                          </span>
                        )}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-text-dim">IPC Transport:</span>
                      <span className="text-accent">stdio (Piped Child stdin/stdout)</span>
                    </div>
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-text-dim">Supervision Guarantee:</span>
                      <span className="text-text">Bounded restarts (&lt;= 5 attempts), orphan job lock</span>
                    </div>
                  </div>

                  {/* Stderr Diagnostics Tail Panel on Failure */}
                  {coreState.type === "failed" && (
                    <div className="space-y-2 border-t border-critical/30 pt-3">
                      <div className="flex items-center justify-between text-xs font-mono text-critical font-semibold">
                        <span>CORE SUPERVISOR FAILURE REASON:</span>
                        <span>{coreState.reason}</span>
                      </div>
                      <div className="p-3 bg-bg border border-border rounded font-mono text-[11px] text-text-dim max-h-48 overflow-y-auto space-y-1">
                        <div className="text-text-faint uppercase font-bold text-[10px] mb-1">
                          --- STDERR TAIL (LAST 50 LINES) ---
                        </div>
                        {coreState.stderr_tail && coreState.stderr_tail.length > 0 ? (
                          coreState.stderr_tail.map((line, idx) => (
                            <div key={idx} className="whitespace-pre-wrap break-all text-critical/90">
                              {line}
                            </div>
                          ))
                        ) : (
                          <div className="text-text-faint">No stderr lines captured.</div>
                        )}
                      </div>
                      <div className="p-2 rounded bg-verify/10 border border-verify/30 text-verify text-xs font-mono">
                        REMEDY: Verify Python virtual environment with <code className="text-text font-bold">make setup</code>.
                      </div>
                    </div>
                  )}

                  {/* Action Bar */}
                  <div className="pt-2 border-t border-border flex items-center justify-between text-[11px] font-mono">
                    <span className="text-text-dim flex items-center gap-1 ml-auto">
                      <Terminal className="w-3.5 h-3.5" />
                      Zero Ports Bound
                    </span>
                  </div>
                </div>
              </div>
              <TerminalPane />
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default App;
