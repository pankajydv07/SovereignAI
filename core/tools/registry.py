"""Registry for typed agent tools and task-class filtering."""

from typing import Any

from tools.base import BaseTool


class ToolRegistry:
    """Registry managing available tools and task-based surface constraints."""

    # Default tool subsets per task class (max 6 tools per class for local model reliability)
    TASK_CLASS_MAP: dict[str, list[str]] = {
        "official_drafting": ["fs_read", "fs_write", "render_deliverable", "calc_exec", "kb_search"],
        "doc_summarise": ["fs_read", "fs_list", "glob", "fs_write", "generate_document", "kb_search"],
        "doc_extract": ["fs_read", "fs_list", "glob", "doc_ingest", "generate_document"],
        "code_generate": ["fs_read", "fs_list", "glob", "fs_write", "code_exec", "generate_document"],
        "code_debug": ["fs_read", "fs_list", "glob", "fs_write", "code_exec"],
        "code": ["fs_read", "fs_list", "glob", "fs_write", "code_exec", "calc_exec"],
        "planner": ["fs_read", "fs_list", "glob"],
        "writer": ["fs_read", "fs_write", "render_deliverable", "calc_exec", "kb_search"],
        "calc": ["fs_read", "fs_write", "code_exec", "calc_exec"],
        "engineering_calc": ["fs_read", "fs_write", "code_exec", "calc_exec"],
        "render": ["fs_read", "fs_write", "render_deliverable"],
        "kb_qa": ["fs_read", "fs_list", "kb_search", "fs_write"],
        "vision_ocr": ["fs_read", "fs_list", "glob", "doc_ingest"],
        "other": ["fs_read", "fs_list", "glob", "fs_write", "generate_document", "calc_exec"],
        "default": ["fs_read", "fs_list", "glob", "fs_write", "generate_document", "calc_exec"],
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


def create_default_tool_registry() -> ToolRegistry:
    """Construct a ToolRegistry populated with all standard built-in SWARAJ tools."""
    from tools.calc_exec import CalcExecTool
    from tools.code_exec import CodeExecTool
    from tools.doc_ingest import DocIngestTool
    from tools.fs_list import FsListTool
    from tools.fs_read import FsReadTool
    from tools.fs_write import FsWriteTool
    from tools.generate_document import GenerateDocumentTool
    from tools.glob import GlobTool
    from tools.kb_search import KbSearchTool
    from tools.render_deliverable import RenderDeliverableTool

    reg = ToolRegistry()
    reg.register(FsReadTool())
    reg.register(FsWriteTool())
    reg.register(FsListTool())
    reg.register(GlobTool())
    reg.register(DocIngestTool())
    reg.register(KbSearchTool())
    reg.register(CalcExecTool())
    reg.register(CodeExecTool())
    reg.register(RenderDeliverableTool())
    reg.register(GenerateDocumentTool())
    return reg
