"""Run budgets and ACP StopReason tracking for SWARAJ agent runtime."""

import time
from dataclasses import dataclass, field
from enum import StrEnum


class StopReason(StrEnum):
    """ACP compliant StopReason enum matching packages/protocol/schema/tool.json."""

    END_TURN = "end_turn"
    MAX_TOKENS = "max_tokens"
    MAX_TURN_REQUESTS = "max_turn_requests"
    REFUSAL = "refusal"
    CANCELLED = "cancelled"


@dataclass
class RunBudget:
    """Configured limits for an agent run per PRD FR-3.6."""

    max_steps: int = 25
    max_run_tokens: int = 128000
    per_call_num_ctx: int = 8192
    wall_clock_timeout_s: float = 300.0


@dataclass
class RunBudgetTracker:
    """Tracks resource consumption against configured run budget during agent execution."""

    budget: RunBudget
    step_count: int = 0
    total_tokens: int = 0
    last_calibrated_prompt_tokens: int = 0
    start_time: float = field(default_factory=time.monotonic)

    def remaining_time_s(self) -> float:
        """Calculate remaining wall-clock time in seconds."""
        elapsed = time.monotonic() - self.start_time
        remaining = self.budget.wall_clock_timeout_s - elapsed
        return max(0.0, remaining)

    def is_timed_out(self) -> bool:
        """Check if wall-clock timeout has expired."""
        return self.remaining_time_s() <= 0.0

    def record_step(self) -> None:
        """Increment executed step counter."""
        self.step_count += 1

    def record_tokens(self, prompt_eval_count: int, eval_count: int) -> None:
        """Record token counts returned from model evaluation."""
        self.last_calibrated_prompt_tokens = prompt_eval_count
        self.total_tokens += prompt_eval_count + eval_count

    def get_stop_reason(self) -> StopReason | None:
        """Determine if budget limits are reached and return corresponding ACP StopReason."""
        if self.step_count >= self.budget.max_steps:
            return StopReason.MAX_TURN_REQUESTS
        if self.total_tokens >= self.budget.max_run_tokens:
            return StopReason.MAX_TOKENS
        return None
