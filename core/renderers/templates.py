"""Template discovery hierarchy and Jinja SandboxedEnvironment manager."""

import os
from pathlib import Path

from jinja2.sandbox import SandboxedEnvironment


class TemplateManager:
    """Manages template discovery hierarchy and SandboxedEnvironment creation.

    Hierarchy:
    1. Workspace override: <workspace>/.swaraj/templates/<template_name>
    2. User/App-level installation: ~/.swaraj/templates/<template_name>
       or %APPDATA%/swaraj/templates
    3. Package default templates directory
    """

    def __init__(self, workspace_root: Path | None = None) -> None:
        self.workspace_root = workspace_root
        self.user_template_dir = self._resolve_user_template_dir()

    def _resolve_user_template_dir(self) -> Path:
        """Resolve app-level template directory."""
        if os.name == "nt":
            appdata = os.getenv("APPDATA")
            if appdata:
                return Path(appdata) / "swaraj" / "templates"
        return Path.home() / ".swaraj" / "templates"

    def find_template(self, template_name: str) -> Path | None:
        """Locate template file according to resolution hierarchy."""
        # 1. Check workspace override
        if self.workspace_root:
            ws_template = self.workspace_root / ".swaraj" / "templates" / template_name
            if ws_template.exists():
                return ws_template

        # 2. Check app/user-level template directory
        user_template = self.user_template_dir / template_name
        if user_template.exists():
            return user_template

        return None

    @staticmethod
    def get_sandboxed_environment() -> SandboxedEnvironment:
        """Return a Jinja2 SandboxedEnvironment to prevent arbitrary code execution."""
        return SandboxedEnvironment(
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
