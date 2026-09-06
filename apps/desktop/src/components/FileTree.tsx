import React, { useState, useEffect } from "react";
import { Folder, FolderOpen, FileText, ChevronRight, ChevronDown, RefreshCw, AlertCircle } from "lucide-react";
import { FileNode } from "../protocol";

interface FileTreeProps {
  workspaceRoot: string;
  onSelectFile?: (path: string) => void;
}

export const FileTree: React.FC<FileTreeProps> = ({ workspaceRoot, onSelectFile }) => {
  const [nodes, setNodes] = useState<FileNode[]>([]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [childrenMap, setChildrenMap] = useState<Record<string, FileNode[]>>({});
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDir = async (relPath?: string): Promise<FileNode[]> => {
    const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    if (!isTauri) {
      // Demo web fallback
      return [
        { name: "core", path: "core", isDir: true },
        { name: "apps", path: "apps", isDir: true },
        { name: "BUILD-ORDERS.md", path: "BUILD-ORDERS.md", isDir: false, sizeBytes: 29783 },
      ];
    }

    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const res = await invoke<FileNode[]>("read_workspace_dir", {
        workspaceRoot,
        relPath: relPath || null,
      });
      return res;
    } catch (err) {
      console.error("Failed to read workspace dir:", err);
      throw err;
    }
  };

  const loadRoot = async () => {
    setLoading(true);
    setError(null);
    try {
      const rootNodes = await fetchDir();
      setNodes(rootNodes);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (workspaceRoot) {
      loadRoot();
    }
  }, [workspaceRoot]);

  const toggleExpand = async (node: FileNode) => {
    if (!node.isDir) return;
    const isExp = !!expanded[node.path];

    if (!isExp && !childrenMap[node.path]) {
      try {
        const children = await fetchDir(node.path);
        setChildrenMap((prev) => ({ ...prev, [node.path]: children }));
      } catch (err) {
        console.error(`Failed to expand ${node.path}:`, err);
      }
    }

    setExpanded((prev) => ({ ...prev, [node.path]: !isExp }));
  };

  const renderNode = (node: FileNode, depth = 0) => {
    const isExp = !!expanded[node.path];
    const children = childrenMap[node.path] || [];

    return (
      <div key={node.path} className="select-none">
        <div
          onClick={() => (node.isDir ? toggleExpand(node) : onSelectFile?.(node.path))}
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
          className="h-7 flex items-center justify-between pr-2 text-xs font-mono text-text-dim hover:text-text hover:bg-surface-2 cursor-pointer transition-colors"
        >
          <div className="flex items-center gap-1.5 min-w-0 truncate">
            {node.isDir ? (
              <>
                {isExp ? <ChevronDown className="w-3.5 h-3.5 shrink-0 text-text-faint" /> : <ChevronRight className="w-3.5 h-3.5 shrink-0 text-text-faint" />}
                {isExp ? <FolderOpen className="w-3.5 h-3.5 shrink-0 text-accent" /> : <Folder className="w-3.5 h-3.5 shrink-0 text-accent" />}
              </>
            ) : (
              <>
                <span className="w-3.5 h-3.5 shrink-0" />
                <FileText className="w-3.5 h-3.5 shrink-0 text-text-faint" />
              </>
            )}
            <span className="truncate">{node.name}</span>
          </div>

          {!node.isDir && node.sizeBytes !== undefined && (
            <span className="text-[10px] text-text-faint font-mono shrink-0">
              {(node.sizeBytes / 1024).toFixed(0)}KB
            </span>
          )}
        </div>

        {/* Capped Warning Marker */}
        {node.isDir && isExp && node.isCapped && (
          <div
            style={{ paddingLeft: `${(depth + 1) * 12 + 8}px` }}
            className="py-1 text-[10px] font-mono text-verify flex items-center gap-1"
          >
            <AlertCircle className="w-3 h-3" />
            <span>Showing 500 of {node.totalEntries} entries</span>
          </div>
        )}

        {/* Children Nodes */}
        {node.isDir && isExp && (
          <div>
            {children.map((child) => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full bg-surface border-r border-border w-64 select-none">
      {/* File Tree Header */}
      <div className="h-10 px-3 border-b border-border flex items-center justify-between font-mono text-xs">
        <span className="font-semibold text-text uppercase tracking-wider text-[11px]">FILE TREE</span>
        <button
          onClick={loadRoot}
          title="Refresh tree"
          className="p-1 rounded-sm bg-surface-2 hover:bg-surface-2/80 border border-border text-text-dim hover:text-text transition-colors cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-accent" : ""}`} />
        </button>
      </div>

      {/* Directory Body */}
      <div className="flex-1 overflow-y-auto py-1">
        {error ? (
          <div className="p-3 m-2 bg-critical/10 border border-critical/30 rounded-sm font-mono text-xs text-critical">
            <div>Failed to read directory</div>
            <div className="text-[10px] text-critical/80 mt-1">{error}</div>
          </div>
        ) : (
          nodes.map((node) => renderNode(node, 0))
        )}
      </div>
    </div>
  );
};
