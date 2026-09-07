"""SWARAJ Policy Engine — Deterministic AUTO / ASK / DENY decision maker."""

import fnmatch
from enum import StrEnum
from typing import Any

from tools.base import SideEffect


class PolicyDecision(StrEnum):
    """Deterministic policy decision."""

    AUTO = "AUTO"
    ASK = "ASK"
    DENY = "DENY"


class PolicyEngine:
    """Deterministic policy decider matching tool + resource_pattern rules.

    `subject` clearance checks are placeholders arriving with Knowledge Base security in M5.
    """

    def __init__(self, session_store: Any | None = None) -> None:
        self.session_store = session_store
        # Volatile in-memory session rules: (project_id, tool, pattern) -> "allow_session"
        self._session_rules: dict[tuple[str, str, str], str] = {}

    def add_session_rule(self, project_id: str, tool: str, resource_pattern: str) -> None:
        """Add volatile session-scoped allow rule."""
        self._session_rules[(project_id, tool, resource_pattern)] = "allow_session"

    async def decide(
        self,
        subject: str | None,
        tool: str,
        resource: str,
        side_effect: SideEffect,
        project_id: str,
    ) -> tuple[PolicyDecision, str | None]:
        """Decide AUTO, ASK, or DENY for a tool call on a resource within a project."""
        # TODO(M5): When user identity and RBAC clearance lands in M5, validate `subject`
        # clearance levels against document classification. For unauthenticated / None subject,
        # fallback is strictly conservative (never permissive).
        if subject is not None and subject.strip() == "":
            subject = None

        # Read side-effects are AUTO by default
        if side_effect == SideEffect.READ:
            return PolicyDecision.AUTO, None

        # Normalize resource string
        res_norm = resource.strip().replace("\\", "/")
        if not res_norm or res_norm == "<unscoped>":
            # Conservative fallback: unscoped resources cannot match generic path patterns
            return PolicyDecision.ASK, None

        # 1. Check volatile session rules
        for (p_id, t_name, pattern), _choice in self._session_rules.items():
            if p_id == project_id and t_name == tool:
                if self._matches_pattern(tool, res_norm, pattern):
                    return PolicyDecision.AUTO, pattern

        # 2. Check persisted database project policies
        if self.session_store and hasattr(self.session_store, "list_project_policies"):
            try:
                db_rules = await self.session_store.list_project_policies(project_id)
                for rule in db_rules:
                    if rule["tool"] == tool:
                        pattern = rule["resourcePattern"]
                        choice = rule["choice"]
                        if self._matches_pattern(tool, res_norm, pattern):
                            if choice in ("always_allow", "allow_session"):
                                return PolicyDecision.AUTO, pattern
                            elif choice == "deny":
                                return PolicyDecision.DENY, pattern
            except Exception as exc:
                log.warning("policy_lookup_failed", project_id=project_id, error=str(exc))

        # Default fallback for write/exec without explicit allow rule is ASK
        return PolicyDecision.ASK, None

    def _matches_pattern(self, tool: str, resource: str, pattern: str) -> bool:
        """Match resource against pattern using glob or command prefix normalization."""
        pat_norm = pattern.strip().replace("\\", "/")

        if tool.startswith("exec") or tool in ("bash", "code_exec", "calc_exec"):
            # Command prefix matching: 'git status *' matches 'git status' or 'git status -s'
            prefix = pat_norm.rstrip("*").strip()
            return resource == prefix or resource.startswith(prefix + " ")
        else:
            # File path glob matching: 'docs/**' or 'notes.md' or '**'
            if pat_norm in ("*", "**"):
                return True
            return fnmatch.fnmatch(resource, pat_norm) or fnmatch.fnmatch(
                resource, "*/" + pat_norm
            )
