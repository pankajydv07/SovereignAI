import React, { useState } from "react";
import { FolderTree, MessageSquare, Cpu, Terminal, Settings } from "lucide-react";

interface NavItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const NAV_ITEMS: NavItem[] = [
  { id: "files", label: "Files", icon: FolderTree },
  { id: "sessions", label: "Sessions", icon: MessageSquare },
  { id: "models", label: "Models", icon: Cpu },
  { id: "terminal", label: "Terminal", icon: Terminal },
];

export const LeftRail: React.FC = () => {
  const [active, setActive] = useState("sessions");

  return (
    <aside className="w-[56px] bg-surface-2 border-r border-border flex flex-col justify-between items-center py-3 shrink-0 select-none">
      {/* Top Nav Group */}
      <div className="flex flex-col items-center gap-2">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = active === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActive(item.id)}
              title={item.label}
              className={`w-10 h-10 rounded flex items-center justify-center transition-colors ${
                isActive
                  ? "bg-surface border border-accent text-accent"
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
          className="w-10 h-10 rounded flex items-center justify-center text-text-dim hover:text-text hover:bg-surface transition-colors"
        >
          <Settings className="w-4 h-4" />
        </button>
      </div>
    </aside>
  );
};
