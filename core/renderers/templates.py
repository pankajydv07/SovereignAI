"""Template discovery hierarchy and Jinja SandboxedEnvironment manager."""

import os
from pathlib import Path

from jinja2.sandbox import SandboxedEnvironment


class MissingOrgTemplateError(RuntimeError):
    """Raised when an approved organisation template is missing for an official deliverable."""

    def __init__(self, template_name: str, searched_paths: list[Path] | None = None) -> None:
        paths_str = ", ".join(str(p) for p in (searched_paths or []))
        message = (
            f"Approved organisation DOCX template '{template_name}' not found. "
            f"Searched: [{paths_str}]. "
            "A PSU approval note in an unapproved layout is not a valid note. "
            f"Register the approved organisation template at '<workspace>/.swaraj/templates/{template_name}' "
            "preserving required schema sections: subject, reference, background, observations, "
            "financial_implication, deviation, recommendation, approval_ladder."
        )
        super().__init__(message)


TEMPLATE_MANIFEST: dict[str, dict[str, str]] = {
    "approval_note.docx": {
        "title": "Representative PSU Approval Note Template",
        "disclaimer": "Representative template — organisation registers its approved template at deployment.",
        "ladder_type": "TWO_LEVEL_MAKER_CHECKER",
    },
    "inspection_summary.docx": {
        "title": "Representative Inspection Summary Template",
        "disclaimer": "Representative template — organisation registers its approved template at deployment.",
        "ladder_type": "TWO_LEVEL_MAKER_CHECKER",
    },
}


class TemplateManager:
    """Manages template discovery hierarchy and SandboxedEnvironment creation.

    Hierarchy:
    1. Workspace override: <workspace>/.swaraj/templates/<template_name>
    2. User/App-level installation: ~/.swaraj/templates/<template_name>
       or %APPDATA%/swaraj/templates
    3. Package default templates directory: core/templates/<template_name>
    """

    def __init__(self, workspace_root: Path | None = None) -> None:
        self.workspace_root = workspace_root
        self.user_template_dir = self._resolve_user_template_dir()
        self.package_template_dir = Path(__file__).parent.parent / "templates"

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

        # 3. Check package default representative template directory
        pkg_template = self.package_template_dir / template_name
        if pkg_template.exists():
            return pkg_template

        return None

    @staticmethod
    def get_sandboxed_environment() -> SandboxedEnvironment:
        """Return a Jinja2 SandboxedEnvironment to prevent arbitrary code execution."""
        return SandboxedEnvironment(
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

