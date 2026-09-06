import React from "react";
import { FolderTree, MessageSquare, Cpu, Terminal, Settings, Home } from "lucide-react";

export type LeftRailTab = "launcher" | "files" | "sessions" | "models" | "terminal";

interface LeftRailProps {
  activeTab: LeftRailTab;
  onTabChange: (tab: LeftRailTab) => void;
}

interface NavItem {
  id: LeftRailTab;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const NAV_ITEMS: NavItem[] = [
  { id: "launcher", label: "Workspaces", icon: Home },
  { id: "sessions", label: "Sessions", icon: MessageSquare },
  { id: "files", label: "File Tree", icon: FolderTree },
  { id: "models", label: "Model Roster", icon: Cpu },
  { id: "terminal", label: "Terminal", icon: Terminal },
];

export const LeftRail: React.FC<LeftRailProps> = ({ activeTab, onTabChange }) => {
  return (
    <aside className="w-[56px] bg-surface-2 border-r border-border flex flex-col justify-between items-center py-3 shrink-0 select-none">
      {/* Top Nav Group */}
      <div className="flex flex-col items-center gap-2">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              title={item.label}
              className={`w-10 h-10 rounded flex items-center justify-center transition-colors cursor-pointer ${
                isActive
                  ? "bg-surface border border-accent text-accent font-semibold"
                  : "text-text-dim hover:text-text hover:bg-surface"
              }`}
            >
              <Icon className="w-4 h-4" />
            </button>
          );
        })}
      </div>

      {/* Bottom Nav Group */}
      <div className="flex flex-col items-center">
        <button
          title="Settings"
          className="w-10 h-10 rounded flex items-center justify-center text-text-dim hover:text-text hover:bg-surface transition-colors cursor-pointer"
        >
          <Settings className="w-4 h-4" />
        </button>
      </div>
    </aside>
  );
};
