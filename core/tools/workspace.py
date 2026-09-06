"""Workspace path safety and isolation utilities."""

from pathlib import Path


class WorkspaceAccessError(PermissionError):
    """Raised when a tool attempts to access a path outside the workspace boundary."""

    def __init__(self, target_path: str | Path, workspace_root: str | Path) -> None:
        self.target_path = Path(target_path)
        self.workspace_root = Path(workspace_root)
        super().__init__(
            f"Access denied: path '{self.target_path}' is outside workspace boundary "
            f"'{self.workspace_root}'"
        )


def verify_workspace_path(path: str | Path, workspace_root: str | Path) -> Path:
    """Verify and resolve a path to ensure it remains strictly within workspace root.

    Resolves symlinks and relative path components (e.g. '../') to prevent path traversal.
    """
    root = Path(workspace_root).resolve()
    target = Path(path)

    # Convert relative paths against workspace root before resolving
    if not target.is_absolute():
        target = root / target

    try:
        resolved_target = target.resolve(strict=False)
    except Exception as exc:
        raise WorkspaceAccessError(path, workspace_root) from exc

    if not resolved_target.is_relative_to(root):
        raise WorkspaceAccessError(path, workspace_root)

    return resolved_target
