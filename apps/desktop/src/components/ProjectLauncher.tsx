import React from "react";
import { Folder, FolderOpen, Shield, Cpu, Trash2, AlertTriangle, RefreshCw } from "lucide-react";
import { ProjectInfo } from "../protocol";
import { UIState } from "../types/ui";
import { StageIndicator } from "./StageIndicator";

interface ProjectLauncherProps {
  projects: ProjectInfo[];
  activeProjectId: string | null;
  uiState: UIState;
  onSelectProject: (project: ProjectInfo) => void;
  onOpenFolder: () => void;
  onRemoveProject: (id: string) => void;
  onRetry: () => void;
  isAirGapped?: boolean;
}

export const ProjectLauncher: React.FC<ProjectLauncherProps> = ({
  projects,
  activeProjectId,
  uiState,
  onSelectProject,
  onOpenFolder,
  onRemoveProject,
  onRetry,
  isAirGapped = true,
}) => {
  return (
    <div className="w-full max-w-4xl mx-auto p-6 space-y-6 select-none">
      {/* Header Banner */}
      <div className="flex items-center justify-between border-b border-border pb-4">
        <div>
          <h1 className="text-lg font-bold text-text flex items-center gap-2">
            <span>SWARAJ</span>
            <span className="font-mono text-xs px-2 py-0.5 rounded-sm bg-surface-2 border border-border text-text-dim">
              v0.1.0
            </span>
          </h1>
          <p className="text-xs text-text-dim mt-0.5">
            Air-gapped confidential AI agent workstation for PSU & industrial operations
          </p>
        </div>

        {/* Sovereignty Status Badge */}
        <div className="flex items-center gap-3 font-mono text-xs">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-sm bg-sovereign/10 border border-sovereign/30 text-sovereign font-semibold">
            <Shield className="w-3.5 h-3.5" />
            <span>{isAirGapped ? "AIR-GAPPED" : "EGRESS MONITORED"}</span>
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-sm bg-surface-2 border border-border text-text-dim">
            <Cpu className="w-3.5 h-3.5 text-accent" />
            <span>LOCAL OLLAMA</span>
          </div>
        </div>
      </div>

      {/* Degraded State Banner */}
      {uiState.type === "degraded" && (
        <div className="p-3 bg-verify/10 border border-verify/30 rounded-sm text-xs font-mono text-verify flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-verify shrink-0" />
            <span>{uiState.message}</span>
          </div>
          <button
            onClick={onRetry}
            className="px-2.5 py-1 rounded-sm bg-verify/20 hover:bg-verify/30 text-verify border border-verify/40 flex items-center gap-1 cursor-pointer transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
            {uiState.remedyLabel}
          </button>
        </div>
      )}

      {/* Main Content Area */}
      <div className="grid grid-cols-3 gap-6">
        {/* Recent Projects Column (Span 2) */}
        <div className="col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold text-text-dim uppercase tracking-wider font-mono">
              Recent Workspaces
            </h2>
            <button
              onClick={onOpenFolder}
              className="px-3 py-1.5 bg-accent text-white hover:bg-accent/90 rounded-sm text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <FolderOpen className="w-3.5 h-3.5" />
              Open Workspace Folder
            </button>
          </div>

          {/* 5 UI States Rendering */}
          {uiState.type === "loading" && (
            <div className="p-8 border border-border rounded-sm bg-surface flex items-center justify-center">
              <StageIndicator label={uiState.stage} elapsedMs={uiState.elapsedMs} />
            </div>
          )}

          {uiState.type === "error" && (
            <div className="p-6 border border-critical/40 rounded-sm bg-critical/5 space-y-3">
              <div className="flex items-center gap-2 text-critical text-xs font-mono font-semibold">
                <AlertTriangle className="w-4 h-4" />
                <span>WORKSPACE LOAD ERROR</span>
              </div>
              <p className="text-xs text-text-dim font-mono">{uiState.message}</p>
              <button
                onClick={onRetry}
                className="px-3 py-1.5 bg-critical/20 hover:bg-critical/30 border border-critical/40 text-critical text-xs font-mono rounded-sm cursor-pointer transition-colors"
              >
                {uiState.remedyLabel}
              </button>
            </div>
          )}

          {uiState.type === "empty" && (
            <div className="p-8 border border-border border-dashed rounded-sm bg-surface text-left space-y-3">
              <div className="text-xs font-semibold text-text">No recent workspace folders found</div>
              <p className="text-xs text-text-dim max-w-md leading-relaxed">
                {uiState.suggestion || "Open an industrial inspection or plant directory to begin."}
              </p>
              <button
                onClick={onOpenFolder}
                className="px-3 py-1.5 bg-surface-2 hover:bg-surface-2/80 border border-border text-accent text-xs font-mono rounded-sm flex items-center gap-1.5 cursor-pointer transition-colors"
              >
                <FolderOpen className="w-3.5 h-3.5" />
                {uiState.actionLabel || "Open Project Folder"}
              </button>
            </div>
          )}

          {(uiState.type === "default" || uiState.type === "degraded") && (
            <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
              {projects.map((proj) => {
                const isActive = proj.id === activeProjectId;
                return (
                  <div
                    key={proj.id}
                    onClick={() => proj.exists && onSelectProject(proj)}
                    tabIndex={0}
                    className={`p-3 border rounded-sm transition-all focus:outline-none focus:ring-2 focus:ring-accent ${
                      isActive
                        ? "bg-surface-2 border-accent text-text"
                        : proj.exists
                        ? "bg-surface hover:bg-surface-2 border-border cursor-pointer"
                        : "bg-surface/50 border-border/50 text-text-dim opacity-75 cursor-not-allowed"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <Folder className={`w-4 h-4 shrink-0 ${proj.exists ? "text-accent" : "text-text-faint"}`} />
                        <div className="truncate">
                          <div className="text-xs font-semibold truncate flex items-center gap-2">
                            <span>{proj.name}</span>
                            {!proj.exists && (
                              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-critical/10 border border-critical/30 text-critical font-normal">
                                Unavailable — directory missing
                              </span>
                            )}
                          </div>
                          <div className="font-mono text-[11px] text-text-dim truncate mt-0.5">
                            {proj.path}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        {!proj.exists && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onRemoveProject(proj.id);
                            }}
                            title="Remove from recent"
                            className="p-1 rounded text-text-dim hover:text-critical hover:bg-critical/10 transition-colors cursor-pointer"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                        <span className="font-mono text-[10px] text-text-faint">
                          {new Date(proj.updatedAtMs).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Model & System Roster (Span 1) */}
        <div className="col-span-1 space-y-3">
          <h2 className="text-xs font-semibold text-text-dim uppercase tracking-wider font-mono">
            Model Roster Status
          </h2>

          <div className="p-4 bg-surface border border-border rounded-sm space-y-3 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-border/60 pb-2">
              <span className="text-text-dim">Planner:</span>
              <span className="text-accent font-semibold">deepseek-r1:14b</span>
            </div>
            <div className="flex items-center justify-between border-b border-border/60 pb-2">
              <span className="text-text-dim">Coder:</span>
              <span className="text-accent font-semibold">qwen3-coder:30b</span>
            </div>
            <div className="flex items-center justify-between border-b border-border/60 pb-2">
              <span className="text-text-dim">Writer:</span>
              <span className="text-accent font-semibold">llama3:8b</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-text-dim">Vision:</span>
              <span className="text-accent font-semibold">llava:13b</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
