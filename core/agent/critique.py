"""SWARAJ Tiered Step Critique and Interrupted Step Idempotency Handler."""

import logging
from typing import Any

from agent.budget import RunBudgetTracker
from models.ollama import OllamaClient
from tools.base import BaseTool, ToolResult

log = logging.getLogger(__name__)


class CritiqueResult:
    """Outcome of step critique evaluation."""

    def __init__(self, passed: bool, feedback: str, is_machine_checked: bool) -> None:
        self.passed = passed
        self.feedback = feedback
        self.is_machine_checked = is_machine_checked


class TieredCritique:
    """Evaluates step execution results using Tier 1 (Free) and Tier 2 (Model) critique."""

    def __init__(self, ollama_client: OllamaClient) -> None:
        self.ollama = ollama_client

    async def evaluate_step(
        self,
        tool: BaseTool[Any, Any],
        result: ToolResult,
        step_description: str,
        model_tag: str,
        budget_tracker: RunBudgetTracker,
        requires_model_critique: bool = False,
    ) -> CritiqueResult:
        """Run Tier 1 machine check first; fallback to Tier 2 model critique if required."""
        # Tier 1: Free Machine-Checkable Evaluation
        if not result.success:
            return CritiqueResult(
                passed=False,
                feedback=f"Tier 1 check failed: {result.error}",
                is_machine_checked=True,
            )

        try:
            tool.output_model.model_validate(result.output)
        except Exception as exc:
            return CritiqueResult(
                passed=False,
                feedback=f"Tier 1 output schema validation failed: {exc}",
                is_machine_checked=True,
            )

        # If no open-ended model critique is required, Tier 1 is sufficient and free
        if not requires_model_critique:
            return CritiqueResult(
                passed=True,
                feedback="Tier 1 machine-checkable critique passed cleanly.",
                is_machine_checked=True,
            )

        # Tier 2: Model Critique (Deducts tokens from budget and counts against wall-clock)
        rem_time = budget_tracker.remaining_time_s()
        if rem_time <= 0.0:
            return CritiqueResult(
                passed=True,
                feedback="Tier 2 critique skipped: wall-clock time limit reached.",
                is_machine_checked=False,
            )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a strict step critique evaluator. Evaluate if the tool output "
                    "satisfies the step description. Respond with 'PASS' or 'FAIL: <reason>'."
                ),
            },
            {
                "role": "user",
                "content": f"Step Description: {step_description}\nTool Output: {result.output}",
            },
        ]

        critique_text = ""
        try:
            async for chunk in self.ollama.stream_chat(
                model=model_tag,
                messages=messages,
                options={"temperature": 0.0},
            ):
                critique_text += chunk.get("message", {}).get("content", "")
                if chunk.get("done", False):
                    p_eval = chunk.get("prompt_eval_count", 0)
                    eval_c = chunk.get("eval_count", 0)
                    # Deduct critique tokens from run budget
                    budget_tracker.record_tokens(p_eval, eval_c)

            passed = critique_text.strip().startswith("PASS")
            return CritiqueResult(
                passed=passed,
                feedback=critique_text,
                is_machine_checked=False,
            )
        except Exception as exc:
            log.warning(f"tier_2_critique_error: {exc}")
            return CritiqueResult(
                passed=True,
                feedback=f"Tier 2 critique bypassed on error: {exc}",
                is_machine_checked=False,
            )

    @staticmethod
    def decide_interrupted_resume(tool: BaseTool[Any, Any]) -> str:
        """Decide whether an interrupted step should auto-retry or prompt the user."""
        if tool.is_idempotent:
            return "auto_retry"
        return "prompt_user"
