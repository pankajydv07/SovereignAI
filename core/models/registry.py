"""SWARAJ Model Registry — Maps roles to model tags from models.yaml.

HARD INVARIANT: No model tag string appears in application code.
Model tags exist ONLY in models.yaml. Application code requests roles.
"""

from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


class Role(StrEnum):
    """Standard SWARAJ role definitions."""

    PLANNER = "planner"
    CODER = "coder"
    WRITER = "writer"
    VISION = "vision"
    EMBEDDER = "embedder"
    CLASSIFIER = "classifier"


class NoAvailableModelForRole(Exception):
    """Raised when no installed or configured model exists for a requested role."""

    def __init__(self, role: str, capability: str | None = None, required_tag: str | None = None) -> None:
        self.role = role
        self.capability = capability
        self.required_tag = required_tag
        msg = f"No model available for role '{role}'"
        if capability:
            msg += f" (capability: '{capability}')"
        if required_tag:
            msg += f". Run `ollama pull {required_tag}`."
        else:
            msg += ". Please configure a model tag in models.yaml."
        super().__init__(msg)


class NoModelForRoleError(NoAvailableModelForRole):
    """Raised when no model tag is configured or resolved for a role."""

    def __init__(self, role: str, available_roles: list[str] | None = None) -> None:
        super().__init__(role)
        self.available_roles = available_roles or []


class ModelNotInstalledError(Exception):
    """Raised during pre-flight validation if a required role model is missing in Ollama."""

    def __init__(self, role: str, tag: str) -> None:
        super().__init__(
            f"Model tag '{tag}' for role '{role}' is not installed in Ollama. "
            f"Run: ollama pull {tag}"
        )
        self.role = role
        self.tag = tag


class ModelRegistry:
    """Model registry managing role resolution, capability merging, and residency policy."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        if config_path is None:
            root_dir = Path(__file__).resolve().parent.parent.parent
            config_path = root_dir / "models.yaml"

        self.config_path = Path(config_path)
        self._roles: dict[str, list[str]] = {}
        self._overrides: dict[str, dict[str, Any]] = {}
        self.margin_floor: float = 0.015
        self.scoring_weights: dict[str, float] = {}
        self.load_config()

    def load_config(self) -> None:
        """Load roles and overrides from models.yaml."""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"models.yaml configuration file not found at {self.config_path}"
            )

        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        self._roles = data.get("roles", {})
        self._overrides = data.get("overrides", {})
        self._priors = data.get("priors", {})
        routing_cfg = data.get("routing", {})
        self.margin_floor = float(routing_cfg.get("margin_floor", 0.015))
        self.scoring_weights = routing_cfg.get("weights", {})

    def resolve(self, role: str | Role) -> str:
        """Resolve a Role to its configured candidate model tag.

        Returns the first candidate model tag from the role list.
        """
        role_str = role.value if isinstance(role, Role) else role
        candidates = self._roles.get(role_str)

        if not candidates or not candidates[0]:
            raise NoModelForRoleError(role_str, list(self._roles.keys()))

        return candidates[0]

    def get_primary(self, role: str | Role) -> str:
        """Alias for resolve() returning the primary model tag for a role."""
        return self.resolve(role)

    def get_overrides(self, model_tag: str) -> dict[str, Any]:
        """Get model overrides (num_ctx, temperature, keep_alive) for a model tag."""
        return self._overrides.get(model_tag, {}).copy()

    def get_num_ctx(self, model_tag: str, discovered_max: int | None = None) -> int:
        """Calculate effective num_ctx = min(discovered_max, yaml_override)."""
        overrides = self.get_overrides(model_tag)
        yaml_ctx = overrides.get("num_ctx")

        if discovered_max is not None and yaml_ctx is not None:
            return min(discovered_max, int(yaml_ctx))
        elif yaml_ctx is not None:
            return int(yaml_ctx)
        elif discovered_max is not None:
            return discovered_max
        return 4096

    def get_keep_alive(self, model_tag: str) -> str:
        """Get keep_alive policy for a model tag (e.g. '30m', '0', '-1')."""
        overrides = self.get_overrides(model_tag)
        return str(overrides.get("keep_alive", "30m"))

    def validate_models(self, installed_tags: set[str]) -> None:
        """Validate pre-flight that every role's resolved model tag is installed in Ollama.

        If a model is missing from installed_tags, raises ModelNotInstalledError immediately.
        """
        for role_name in self._roles:
            try:
                candidate_tag = self.resolve(role_name)
                if candidate_tag not in installed_tags:
                    raise ModelNotInstalledError(role_name, candidate_tag)
            except NoModelForRoleError:
                continue

    def get_role_fulfilment_status(
        self, installed_tags: set[str], running_models: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Generate PRD FR-2.8 Role Fulfilment status data for all standard roles."""
        running_map = {
            m.get("name") or m.get("model"): m for m in running_models if isinstance(m, dict)
        }
        fulfilment: list[dict[str, Any]] = []

        for role_enum in Role:
            role_name = role_enum.value
            try:
                tag = self.resolve(role_name)
                is_installed = tag in installed_tags
                is_resident = tag in running_map

                residency_str = "UNLOADED"
                vram_str = "0 MB"

                if is_resident:
                    residency_str = "RESIDENT"
                    running_info = running_map[tag]
                    vram_bytes = running_info.get("size_vram", 0)
                    vram_mb = round(vram_bytes / (1024 * 1024), 1)
                    vram_str = f"{vram_mb} MB"

                if is_installed:
                    fulfilment.append(
                        {
                            "role": role_name,
                            "satisfied": True,
                            "modelTag": tag,
                            "residency": residency_str,
                            "vramUsage": vram_str,
                            "consequence": None,
                        }
                    )
                else:
                    fulfilment.append(
                        {
                            "role": role_name,
                            "satisfied": False,
                            "modelTag": tag,
                            "residency": "MISSING",
                            "vramUsage": "0 MB",
                            "consequence": (
                                f"Role '{role_name}' unavailable: '{tag}' is not installed. "
                                f"Run: ollama pull {tag}"
                            ),
                        }
                    )
            except NoModelForRoleError:
                fulfilment.append(
                    {
                        "role": role_name,
                        "satisfied": False,
                        "modelTag": None,
                        "residency": "UNCONFIGURED",
                        "vramUsage": "0 MB",
                        "consequence": (
                            f"No model tag assigned for role '{role_name}' in models.yaml."
                        ),
                    }
                )

        return fulfilment
