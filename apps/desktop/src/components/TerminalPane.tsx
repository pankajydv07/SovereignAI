import React, { useEffect, useRef, useState, useCallback } from "react";
import { Terminal as XTerm } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebglAddon } from "@xterm/addon-webgl";
import "@xterm/xterm/css/xterm.css";
import { Terminal as TerminalIcon, Plus, X, Maximize2, Minimize2, ChevronDown, ChevronUp } from "lucide-react";

interface TerminalTab {
  id: string;
  name: string;
  exitCode?: number | null;
}

interface PtyOutputPayload {
  id: string;
  data: number[];
}

interface PtyExitPayload {
  id: string;
  exit_code: number | null;
}

interface SingleTerminalProps {
  tab: TerminalTab;
  isActive: boolean;
  onExit: (id: string, exitCode: number | null) => void;
}

const SingleTerminal: React.FC<SingleTerminalProps> = ({ tab, isActive, onExit }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<XTerm | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const webglAddonRef = useRef<WebglAddon | null>(null);
  const resizeTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Initialize xterm instance with design lock tokens
    const term = new XTerm({
      fontFamily: "'IBM Plex Mono', monospace",
      fontSize: 12,
      lineHeight: 1.2,
      cursorBlink: true,
      scrollback: 10000,
      theme: {
        background: "#0B0F14",
        foreground: "#E6EDF3",
        cursor: "#4C8DF6",
        selectionBackground: "#263241",
        black: "#0B0F14",
        red: "#EF4444",
        green: "#10B981",
        yellow: "#F59E0B",
        blue: "#4C8DF6",
        magenta: "#8B5CF6",
        cyan: "#06B6D4",
        white: "#E6EDF3",
      },
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(containerRef.current);

    // Hardware acceleration with fallback
    try {
      const webglAddon = new WebglAddon();
      term.loadAddon(webglAddon);
      webglAddonRef.current = webglAddon;
    } catch {
      // Fallback to standard canvas renderer if WebGL unavailable
    }

    xtermRef.current = term;
    fitAddonRef.current = fitAddon;

    const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

    // Initial resize & spawn
    const initPty = async () => {
      fitAddon.fit();
      const dims = fitAddon.proposeDimensions();
      const rows = Math.max(1, dims?.rows || 24);
      const cols = Math.max(1, dims?.cols || 80);

      if (isTauri) {
        try {
          const { invoke } = await import("@tauri-apps/api/core");
          await invoke("create_pty", { id: tab.id, rows, cols, cwd: null });
        } catch (err) {
          term.writeln(`\r\n\x1b[31mFailed to spawn PTY: ${err}\x1b[0m\r\n`);
        }
      } else {
        term.writeln("\r\n\x1b[33m[SWARAJ Demo Mode] PTY stream initialized. (Web fallback)\x1b[0m\r\n$ ");
      }
    };

    initPty();

    // User input handler:
    // NOTE: write_pty is designated strictly for USER interactive terminal input.
    // Agent-initiated commands in P4.2 must execute via sandboxed runners and policy checks.
    const textEncoder = new TextEncoder();
    const disposableOnData = term.onData(async (dataStr) => {
      if (isTauri) {
        try {
          const { invoke } = await import("@tauri-apps/api/core");
          const byteArray = Array.from(textEncoder.encode(dataStr));
          await invoke("write_pty", { id: tab.id, data: byteArray });
        } catch (err) {
          console.error("write_pty failed:", err);
        }
      } else {
        // Echo demo mode
        if (dataStr === "\r") {
          term.write("\r\n$ ");
        } else {
          term.write(dataStr);
        }
      }
    });

    // Subscriptions for Tauri IPC PTY events
    let unlistenOutput: (() => void) | undefined;
    let unlistenExit: (() => void) | undefined;

    if (isTauri) {
      import("@tauri-apps/api/event").then(({ listen }) => {
        listen<PtyOutputPayload>("pty-output", (event) => {
          if (event.payload.id === tab.id && xtermRef.current) {
            // Binary byte streaming: Uint8Array written to xterm
            xtermRef.current.write(new Uint8Array(event.payload.data));
          }
        }).then((fn) => (unlistenOutput = fn));

        listen<PtyExitPayload>("pty-exit", (event) => {
          if (event.payload.id === tab.id) {
            const code = event.payload.exit_code;
            if (xtermRef.current) {
              xtermRef.current.write(`\r\n\x1b[33m[Process exited with code ${code ?? 0}]\x1b[0m\r\n`);
            }
            onExit(tab.id, code);
          }
        }).then((fn) => (unlistenExit = fn));
      });
    }

    return () => {
      disposableOnData.dispose();
      if (unlistenOutput) unlistenOutput();
      if (unlistenExit) unlistenExit();

      if (isTauri) {
        import("@tauri-apps/api/core").then(({ invoke }) => {
          invoke("close_pty", { id: tab.id }).catch((err) => {
            console.debug("close_pty error:", err);
          });
        });
      }

      if (webglAddonRef.current) {
        try {
          webglAddonRef.current.dispose();
        } catch (err) {
          console.debug("webgl dispose error:", err);
        }
      }
      term.dispose();
    };
  }, [tab.id]);

  // Debounced ResizeObserver (~80ms trailing)
  useEffect(() => {
    if (!containerRef.current || !isActive) return;

    const handleResize = () => {
      if (resizeTimeoutRef.current) clearTimeout(resizeTimeoutRef.current);

      resizeTimeoutRef.current = setTimeout(async () => {
        if (!fitAddonRef.current || !xtermRef.current) return;
        fitAddonRef.current.fit();
        const dims = fitAddonRef.current.proposeDimensions();
        const rows = Math.max(1, dims?.rows || 24);
        const cols = Math.max(1, dims?.cols || 80);

        const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
        if (isTauri) {
          try {
            const { invoke } = await import("@tauri-apps/api/core");
            await invoke("resize_pty", { id: tab.id, rows, cols });
          } catch (err) {
            console.error("resize_pty error:", err);
          }
        }
      }, 80);
    };

    // Re-fit on active tab switch
    handleResize();

    const observer = new ResizeObserver(handleResize);
    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      if (resizeTimeoutRef.current) clearTimeout(resizeTimeoutRef.current);
    };
  }, [isActive, tab.id]);

  return (
    <div
      style={{ display: isActive ? "block" : "none" }}
      className="w-full h-full bg-[#0B0F14] overflow-hidden relative"
    >
      <div ref={containerRef} className="w-full h-full p-2" />
    </div>
  );
};

export const TerminalPane: React.FC = () => {
  const [tabs, setTabs] = useState<TerminalTab[]>([
    { id: "term-1", name: "Terminal 1" },
  ]);
  const [activeTabId, setActiveTabId] = useState<string>("term-1");
  const [isMinimized, setIsMinimized] = useState<boolean>(false);
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const nextTabNum = useRef<number>(2);

  const handleAddTab = () => {
    const id = `term-${Date.now()}`;
    const name = `Terminal ${nextTabNum.current++}`;
    setTabs((prev) => [...prev, { id, name }]);
    setActiveTabId(id);
    setIsMinimized(false);
  };

  const handleCloseTab = (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();

    setTabs((prev) => {
      const remaining = prev.filter((t) => t.id !== id);
      if (remaining.length === 0) {
        // Always keep at least 1 terminal tab active
        const newId = `term-${Date.now()}`;
        setActiveTabId(newId);
        return [{ id: newId, name: "Terminal 1" }];
      }
      if (activeTabId === id) {
        setActiveTabId(remaining[remaining.length - 1].id);
      }
      return remaining;
    });
  };

  const handleProcessExit = useCallback((id: string, exitCode: number | null) => {
    setTabs((prev) =>
      prev.map((t) => (t.id === id ? { ...t, exitCode } : t))
    );
  }, []);

  return (
    <div
      className={`flex flex-col bg-bg border-t border-border transition-all duration-150 ${
        isMinimized ? "h-[30px]" : isExpanded ? "h-96" : "h-64"
      }`}
    >
      {/* 30px Tab Bar */}
      <div className="h-[30px] bg-surface border-b border-border flex items-center justify-between px-2 select-none font-mono text-xs">
        <div className="flex items-center gap-1 overflow-x-auto no-scrollbar">
          <div className="flex items-center gap-1 text-text-dim pr-2 border-r border-border mr-1">
            <TerminalIcon className="w-3.5 h-3.5 text-accent" />
            <span className="text-[11px] font-semibold tracking-wider">PTY</span>
          </div>

          {tabs.map((tab) => {
            const isActive = tab.id === activeTabId;
            return (
              <div
                key={tab.id}
                onClick={() => {
                  setActiveTabId(tab.id);
                  if (isMinimized) setIsMinimized(false);
                }}
                className={`h-6 px-2.5 rounded-t flex items-center gap-2 cursor-pointer transition-colors border-t border-x text-[11px] ${
                  isActive
                    ? "bg-[#0B0F14] text-text border-border font-semibold"
                    : "bg-surface-2 text-text-dim border-transparent hover:text-text hover:bg-surface-2/80"
                }`}
              >
                <span>{tab.name}</span>
                {tab.exitCode !== undefined && tab.exitCode !== null && (
                  <span className="text-[9px] px-1 rounded bg-verify/20 text-verify font-mono">
                    [{tab.exitCode}]
                  </span>
                )}
                {tabs.length > 1 && (
                  <button
                    onClick={(e) => handleCloseTab(tab.id, e)}
                    className="hover:text-critical p-0.5 rounded text-text-faint transition-colors"
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}
              </div>
            );
          })}

          <button
            onClick={handleAddTab}
            className="h-6 px-1.5 rounded hover:bg-surface-2 text-text-dim hover:text-accent transition-colors cursor-pointer flex items-center justify-center ml-1"
            title="New Terminal Tab"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={() => setIsMinimized(!isMinimized)}
            className="p-1 text-text-dim hover:text-text rounded transition-colors cursor-pointer"
            title={isMinimized ? "Restore Terminal" : "Minimize Terminal"}
          >
            {isMinimized ? (
              <ChevronUp className="w-3.5 h-3.5" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5" />
            )}
          </button>
          {!isMinimized && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-1 text-text-dim hover:text-text rounded transition-colors cursor-pointer"
              title={isExpanded ? "Collapse Size" : "Maximize Size"}
            >
              {isExpanded ? (
                <Minimize2 className="w-3.5 h-3.5" />
              ) : (
                <Maximize2 className="w-3.5 h-3.5" />
              )}
            </button>
          )}
        </div>
      </div>

      {/* Terminal Viewport - All containers kept mounted to preserve state & scrollback */}
      <div className={`flex-1 relative overflow-hidden bg-[#0B0F14] ${isMinimized ? "hidden" : "block"}`}>
        {tabs.map((tab) => (
          <SingleTerminal
            key={tab.id}
            tab={tab}
            isActive={tab.id === activeTabId}
            onExit={handleProcessExit}
          />
        ))}
      </div>
    </div>
  );
};

export default TerminalPane;
