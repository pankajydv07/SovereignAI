"""Registry for typed agent tools and task-class filtering."""

from typing import Any

from tools.base import BaseTool


class ToolRegistry:
    """Registry managing available tools and task-based surface constraints."""

    # Default tool subsets per task class (max 6 tools per class for local model reliability)
    TASK_CLASS_MAP: dict[str, list[str]] = {
        "code": ["fs_read", "fs_list", "glob", "fs_write"],
        "planner": ["fs_read", "fs_list", "glob"],
        "writer": ["fs_read", "fs_write"],
        "default": ["fs_read", "fs_list", "glob", "fs_write"],
    }

    MAX_TOOLS_PER_TASK: int = 6

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool[Any, Any]] = {}

    def register(self, tool: BaseTool[Any, Any]) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool[Any, Any] | None:
        """Retrieve a registered tool by name."""
        return self._tools.get(name)

    def list_all(self) -> list[BaseTool[Any, Any]]:
        """List all registered tools."""
        return list(self._tools.values())

    def get_tools_for_task(self, task_class: str) -> list[BaseTool[Any, Any]]:
        """Return a filtered list of tools for a task class, capped at 6 tools maximum."""
        allowed_names = self.TASK_CLASS_MAP.get(task_class, self.TASK_CLASS_MAP["default"])
        filtered = [tool for name, tool in self._tools.items() if name in allowed_names]

        # Enforce hard ceiling of MAX_TOOLS_PER_TASK (6 tools)
        return filtered[: self.MAX_TOOLS_PER_TASK]

    def to_ollama_tools(self, task_class: str | None = None) -> list[dict[str, Any]]:
        """Export Ollama tool function schemas for the selected task class or all tools."""
        tools = self.get_tools_for_task(task_class) if task_class else self.list_all()
        return [tool.to_ollama_tool() for tool in tools]
