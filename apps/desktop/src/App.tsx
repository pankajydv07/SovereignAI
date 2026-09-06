import React, { useEffect, useReducer, useState } from "react";
import { TopBar } from "./components/TopBar";
import { LeftRail, LeftRailTab } from "./components/LeftRail";
import { ConversationPane } from "./components/ConversationPane";
import { TerminalPane } from "./components/TerminalPane";
import { SovereigntyScreen, SovereigntyStatus } from "./components/SovereigntyScreen";
import { ProjectLauncher } from "./components/ProjectLauncher";
import { SessionList } from "./components/SessionList";
import { FileTree } from "./components/FileTree";
import { ReviewApprovePanel } from "./components/ReviewApprovePanel";
import { PIDAnalysisView } from "./components/PIDAnalysisView";
import { CoreState, ProjectInfo } from "./protocol";
import { initialProjectState, projectReducer } from "./reducers/projectReducer";
import { initialSessionState, sessionReducer } from "./reducers/sessionReducer";
import { Shield, Zap, MessageSquare, FileCheck, Layers } from "lucide-react";

export const App: React.FC = () => {
  const [coreState, setCoreState] = useState<CoreState>({ type: "connecting" });
  const [activeTab, setActiveTab] = useState<"chat" | "diagnostics" | "sovereignty" | "review" | "pid">("chat");
  const [leftRailTab, setLeftRailTab] = useState<LeftRailTab>("launcher");
  const [egressCount, setEgressCount] = useState<number>(0);
  const [isAirGapped, setIsAirGapped] = useState<boolean>(true);

  const [projState, dispatchProj] = useReducer(projectReducer, initialProjectState);
  const [sessState, dispatchSess] = useReducer(sessionReducer, initialSessionState);

  const activeProject = projState.projects.find((p) => p.id === projState.activeProjectId) || null;

  // Initial setup & Tauri IPC event subscriptions
  useEffect(() => {
    const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

    if (!isTauri) {
      setCoreState({ type: "ready", version: "0.1.0", protocol_version: "2026-03-01" });
      dispatchProj({
        type: "SET_PROJECTS",
        payload: [
          {
            id: "proj-demo-1",
            name: "IOCL Gujarat Refinery Inspection",
            path: "d:/SovereignAI",
            createdAtMs: Date.now() - 86400000,
            updatedAtMs: Date.now(),
            exists: true,
          },
        ],
      });
      dispatchSess({
        type: "SET_SESSIONS",
        payload: [
          {
            sessionId: "sess-demo-01",
            projectId: "proj-demo-1",
            title: "Crude Distillation Column Review",
            status: "active",
            createdAtMs: Date.now() - 3600000,
            updatedAtMs: Date.now(),
          },
        ],
      });
      return;
    }

    let unlistenFn: (() => void) | undefined;
    let unlistenSov: (() => void) | undefined;

    const setupApp = async () => {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        const { listen } = await import("@tauri-apps/api/event");

        const status = await invoke<CoreState>("get_core_status");
        setCoreState(status);

        const sovStatus = await invoke<SovereigntyStatus>("get_sovereignty_status");
        setEgressCount(sovStatus.egress_count);
        setIsAirGapped(!sovStatus.active_link);

        // Fetch recent projects from Rust
        dispatchProj({ type: "SET_LOADING", stage: "loading recent projects...", elapsedMs: 100 });
        const recent = await invoke<ProjectInfo[]>("get_recent_projects");
        dispatchProj({ type: "SET_PROJECTS", payload: recent });

        unlistenFn = await listen<CoreState>("core-status-changed", (event) => {
          setCoreState(event.payload);
          if (event.payload.type === "failed" || event.payload.type === "restarting") {
            dispatchSess({
              type: "SET_DEGRADED",
              message: "Agent core unavailable — projects can be opened, sessions unavailable.",
              remedyLabel: "Retry Core",
            });
          }
        });

        unlistenSov = await listen<SovereigntyStatus>("sovereignty-status-changed", (event) => {
          setEgressCount(event.payload.egress_count);
          setIsAirGapped(!event.payload.active_link);
        });
      } catch (err) {
        dispatchProj({ type: "SET_ERROR", message: String(err), remedyLabel: "Retry Load" });
      }
    };

    setupApp();

    return () => {
      if (unlistenFn) unlistenFn();
      if (unlistenSov) unlistenSov();
    };
  }, []);

  const fetchSessionsForProject = async (project: ProjectInfo) => {
    const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    if (!isTauri) return;

    dispatchSess({ type: "SET_LOADING", stage: "fetching session list...", elapsedMs: 50 });
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const res = await invoke<any>("invoke_core_rpc", {
        method: "session/list",
        params: { projectId: project.id, projectPath: project.path },
      });
      dispatchSess({ type: "SET_SESSIONS", payload: res.sessions || [] });
    } catch (err) {
      dispatchSess({
        type: "SET_DEGRADED",
        message: "Agent core unavailable — projects can be opened, sessions unavailable.",
        remedyLabel: "Retry Core",
      });
    }
  };

  const handleSelectProject = (project: ProjectInfo) => {
    dispatchProj({ type: "SET_ACTIVE_PROJECT", id: project.id });
    setLeftRailTab("sessions");
    fetchSessionsForProject(project);
  };

  const handleOpenFolder = async () => {
    const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    const selected = window.prompt("Enter absolute project folder path:");
    if (!selected || !selected.trim()) return;
    const path = selected.trim();
    const folderName = path.split(/[\/\\]/).pop() || path;
    const newProj: ProjectInfo = {
      id: `proj-${Date.now()}`,
      name: folderName,
      path: path,
      createdAtMs: Date.now(),
      updatedAtMs: Date.now(),
      exists: true,
    };
    if (isTauri) {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        const updated = await invoke<ProjectInfo[]>("add_recent_project", { project: newProj });
        dispatchProj({ type: "SET_PROJECTS", payload: updated });
      } catch (err) {
        console.error("Failed to add recent project:", err);
      }
    } else {
      dispatchProj({ type: "ADD_PROJECT", payload: newProj });
    }
    handleSelectProject(newProj);
  };

  const handleRemoveProject = async (id: string) => {
    const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    if (!isTauri) {
      dispatchProj({ type: "REMOVE_PROJECT", id });
      return;
    }
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const updated = await invoke<ProjectInfo[]>("remove_recent_project", { id });
      dispatchProj({ type: "SET_PROJECTS", payload: updated });
    } catch (err) {
      console.error("Failed to remove project:", err);
    }
  };

  const handleNewSession = async () => {
    if (!activeProject) return;
    const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    if (!isTauri) return;

    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const newSess = await invoke<any>("invoke_core_rpc", {
        method: "session/new",
        params: { projectId: activeProject.id, projectPath: activeProject.path },
      });
      dispatchSess({ type: "ADD_SESSION", payload: newSess });
      setActiveTab("chat");
    } catch (err) {
      console.error("Failed to create new session:", err);
    }
  };

  const handleSelectSession = async (sessionId: string) => {
    if (!activeProject) return;
    const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    if (!isTauri) {
      dispatchSess({ type: "SET_ACTIVE_SESSION", id: sessionId });
      setActiveTab("chat");
      return;
    }

    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const res = await invoke<any>("invoke_core_rpc", {
        method: "session/load",
        params: { sessionId, projectPath: activeProject.path },
      });
      dispatchSess({ type: "SET_SESSION_LOADED", session: res.session, events: res.events });
      setActiveTab("chat");
    } catch (err) {
      console.error("Failed to load session:", err);
    }
  };

  const handleCloseSession = async (sessionId: string) => {
    if (!activeProject) return;
    const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    if (!isTauri) {
      dispatchSess({ type: "UPDATE_SESSION_STATUS", id: sessionId, status: "closed" });
      return;
    }
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("invoke_core_rpc", {
        method: "session/close",
        params: { sessionId, projectPath: activeProject.path },
      });
      dispatchSess({ type: "UPDATE_SESSION_STATUS", id: sessionId, status: "closed" });
    } catch (err) {
      console.error("Failed to close session:", err);
    }
  };

  const handleKillCore = async () => {
    const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    if (isTauri) {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("kill_core_process");
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
        <LeftRail activeTab={leftRailTab} onTabChange={setLeftRailTab} />

        {/* Dynamic Sidebar Drawer */}
        {leftRailTab === "sessions" && (
          <SessionList
            sessions={sessState.sessions}
            activeSessionId={sessState.activeSessionId}
            uiState={sessState.uiState}
            onSelectSession={handleSelectSession}
            onNewSession={handleNewSession}
            onCloseSession={handleCloseSession}
            onRetry={() => activeProject && fetchSessionsForProject(activeProject)}
          />
        )}

        {leftRailTab === "files" && (
          <FileTree workspaceRoot={activeProject ? activeProject.path : "d:/SovereignAI"} />
        )}

        {/* Content Viewport */}
        <main className="flex-1 flex flex-col bg-bg overflow-hidden">
          {leftRailTab === "launcher" ? (
            <ProjectLauncher
              projects={projState.projects}
              activeProjectId={projState.activeProjectId}
              uiState={projState.uiState}
              onSelectProject={handleSelectProject}
              onOpenFolder={handleOpenFolder}
              onRemoveProject={handleRemoveProject}
              onRetry={() => {
                const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
                if (isTauri) {
                  import("@tauri-apps/api/core").then(({ invoke }) =>
                    invoke<ProjectInfo[]>("get_recent_projects").then((p) =>
                      dispatchProj({ type: "SET_PROJECTS", payload: p })
                    )
                  );
                }
              }}
              isAirGapped={isAirGapped}
            />
          ) : (
            <>
              {/* Console Sub-Header */}
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
                    onClick={() => setActiveTab("review")}
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
                    onClick={() => setActiveTab("pid")}
                    className={`px-3 py-1 rounded text-[11px] flex items-center gap-1.5 transition-colors cursor-pointer ${
                      activeTab === "pid"
                        ? "bg-surface-2 text-[#06B6D4] font-semibold border border-border"
                        : "text-text-dim hover:text-text"
                    }`}
                  >
                    <Layers className="w-3.5 h-3.5 text-[#06B6D4]" />
                    <span>P&ID VISION</span>
                  </button>
                </div>

                <div className="flex items-center gap-2 font-mono text-[11px]">
                  {process.env.NODE_ENV !== "production" && (
                    <button
                      onClick={handleKillCore}
                      className="px-2 py-0.5 rounded bg-critical/10 border border-critical/30 text-critical hover:bg-critical/20 flex items-center gap-1 transition-colors cursor-pointer"
                    >
                      <Zap className="w-3 h-3" />
                      Simulate Crash
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

              {activeTab === "review" && (
                <ReviewApprovePanel
                  deliverableId="DELIV-2026-09-C101"
                  title="TECHNICAL APPROVAL NOTE: Remaining Life & Inspection Sanction"
                  subject="Crude Distillation Column C-101 Remaining Life & Inspection Sanction"
                  maker={{ id: "user_sharma", name: "A. Sharma", designation: "Senior Inspection Engineer" }}
                  checker={{ id: "user_kulkarni", name: "P. V. Kulkarni", designation: "Chief Manager - Mechanical" }}
                  currentUser={{ id: "user_kulkarni", name: "P. V. Kulkarni", designation: "Chief Manager - Mechanical" }}
                />
              )}

              {activeTab === "pid" && <PIDAnalysisView />}
            </>
          )}
        </main>
      </div>
    </div>
  );
};

export default App;
