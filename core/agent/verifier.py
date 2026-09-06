"""Code Verifier Loop Strategy — Multi-iteration test-driven repair in sandbox."""

import asyncio
from dataclasses import dataclass, field
import difflib
import logging
from pathlib import Path
from typing import Any

from agent.budget import StopReason
from agent.turn_loop import RunBudgetExhausted, TurnCancelledError, TurnLoop
from tools.base import ToolContext, ToolResult
from tools.code_exec import CodeExecInput, CodeExecOutput, CodeExecTool

log = logging.getLogger(__name__)


@dataclass
class VerifierResult:
    """Result returned by CodeVerifierStrategy."""

    success: bool
    iterations: int
    duration_ms: int
    final_code: str
    final_test_code: str | None
    last_exec_output: CodeExecOutput
    test_passed: bool | None
    test_modified: bool = False
    diagnostic_report: dict[str, Any] | None = None
    ui_label: str = "Executed"  # "Verified in sandbox" when unit tests pass with exit code 0


def extract_failing_test_names(stderr_tail: list[str]) -> list[str]:
    """Extract failing pytest test names from stderr/stdout log lines."""
    failing: list[str] = []
    for line in stderr_tail:
        line_str = line.strip()
        if "FAILED " in line_str or "ERROR " in line_str:
            parts = line_str.split()
            for p in parts:
                if "::" in p or p.startswith("test_"):
                    failing.append(p)
    return failing if failing else ["test_execution_failure"]


def compute_code_diff(old_code: str, new_code: str) -> str:
    """Compute unified diff between code iterations."""
    diff_lines = list(
        difflib.unified_diff(
            old_code.splitlines(keepends=True),
            new_code.splitlines(keepends=True),
            fromfile="iteration_prev.py",
            tofile="iteration_curr.py",
        )
    )
    return "".join(diff_lines)


class CodeVerifierStrategy:
    """Strategy executing code + unit tests in sandbox with budget tracking and repair."""

    MAX_VERIFIER_ITERATIONS: int = 3

    def __init__(self, turn_loop: TurnLoop) -> None:
        self.turn_loop = turn_loop

    async def run_verifier(
        self,
        session_id: str,
        model_tag: str,
        code: str,
        test_code: str | None = None,
        step_approval_granted: bool = True,
        tool_context: ToolContext | None = None,
    ) -> VerifierResult:
        """Run up to 3 repair iterations of code + test execution under single step approval grant."""
        start_time_ms = int(asyncio.get_event_loop().time() * 1000)
        code_exec_tool: CodeExecTool | None = self.turn_loop.registry.get("code_exec")  # type: ignore[assignment]
        if not code_exec_tool:
            code_exec_tool = CodeExecTool()

        ctx = tool_context or ToolContext(workspace_root=Path("."))
        initial_test_code = test_code

        current_code = code
        current_test_code = test_code
        test_modified = False
        iteration = 1
        last_output: CodeExecOutput | None = None

        while iteration <= self.MAX_VERIFIER_ITERATIONS:
            if self.turn_loop._cancelled:
                raise TurnCancelledError(partial_results=[])

            # Check budget limits before iteration execution
            stop_reason = self.turn_loop.tracker.get_stop_reason()
            if stop_reason:
                raise RunBudgetExhausted(stop_reason, partial_results=[])

            rem_time = self.turn_loop.tracker.remaining_time_s()
            if rem_time <= 0.0:
                raise RunBudgetExhausted(StopReason.MAX_TOKENS, partial_results=[])

            # Execute code_exec tool under the step's single approval grant
            exec_args = CodeExecInput(
                code=current_code,
                test_code=current_test_code,
                timeout_s=min(60.0, rem_time),
            )

            tool_res: ToolResult = await code_exec_tool.run(exec_args, ctx)
            output_dict = tool_res.output if isinstance(tool_res.output, dict) else {}
            last_output = CodeExecOutput(**output_dict) if output_dict else CodeExecOutput(
                run_id="failed",
                exit_code=-1,
                stdout_tail=[],
                stderr_tail=[tool_res.error or "Execution failed"],
                duration_ms=0,
                timed_out=False,
                output_artifacts=[],
                test_passed=False if current_test_code else None,
            )

            # Determine primary truth for test_passed from exit code 0
            test_passed = (last_output.exit_code == 0) if current_test_code is not None else None
            ui_label = "Verified in sandbox" if (test_passed is True) else "Executed"

            # Log sub-step event in SessionStore
            if self.turn_loop.session_store and hasattr(self.turn_loop.session_store, "append_event"):
                await self.turn_loop.session_store.append_event(
                    session_id=session_id,
                    event_type="verifier_step",
                    data={
                        "iteration": iteration,
                        "exit_code": last_output.exit_code,
                        "test_passed": test_passed,
                        "test_modified": test_modified,
                        "duration_ms": last_output.duration_ms,
                        "ui_label": ui_label,
                    },
                )

            # Success condition: exit_code == 0 and (no tests or test_passed is True)
            if last_output.exit_code == 0:
                end_time_ms = int(asyncio.get_event_loop().time() * 1000)
                return VerifierResult(
                    success=True,
                    iterations=iteration,
                    duration_ms=end_time_ms - start_time_ms,
                    final_code=current_code,
                    final_test_code=current_test_code,
                    last_exec_output=last_output,
                    test_passed=test_passed,
                    test_modified=test_modified,
                    ui_label=ui_label,
                )

            # Reached max iterations without success -> Surface structured diagnostic report
            if iteration >= self.MAX_VERIFIER_ITERATIONS:
                failing_tests = extract_failing_test_names(last_output.stderr_tail + last_output.stdout_tail)
                code_diff = compute_code_diff(code, current_code)

                diagnostic_report = {
                    "failing_tests": failing_tests,
                    "stderr_tail": last_output.stderr_tail,
                    "stdout_tail": last_output.stdout_tail,
                    "code_diff": code_diff,
                    "test_modified": test_modified,
                    "user_options": [
                        "Retry with guidance",
                        "Edit manually",
                        "Skip",
                        "Re-plan",
                    ],
                }

                end_time_ms = int(asyncio.get_event_loop().time() * 1000)
                return VerifierResult(
                    success=False,
                    iterations=iteration,
                    duration_ms=end_time_ms - start_time_ms,
                    final_code=current_code,
                    final_test_code=current_test_code,
                    last_exec_output=last_output,
                    test_passed=False,
                    test_modified=test_modified,
                    diagnostic_report=diagnostic_report,
                    ui_label="Verification Failed",
                )

            # Count repair turn against run budget steps!
            self.turn_loop.tracker.record_step()

            # Construct repair prompt for model
            failing_tests = extract_failing_test_names(last_output.stderr_tail + last_output.stdout_tail)
            stderr_context = "\n".join(last_output.stderr_tail[-20:])

            repair_prompt = (
                f"Repair Iteration {iteration} Execution Failure:\n"
                f"Failing tests: {failing_tests}\n"
                f"Error Output:\n{stderr_context}\n\n"
                "Please fix the code implementation. Do NOT modify unit test assertions unless explicitly instructed."
            )

            repair_messages = [
                {"role": "user", "content": repair_prompt}
            ]

            # Request repair output from model via turn loop client
            rem_time = self.turn_loop.tracker.remaining_time_s()
            if rem_time <= 0.0:
                raise RunBudgetExhausted(StopReason.MAX_TOKENS, partial_results=[])

            model_response = ""
            async for chunk in self.turn_loop.ollama.stream_chat(
                model=model_tag,
                messages=repair_messages,
            ):
                if self.turn_loop._cancelled:
                    raise TurnCancelledError(partial_results=[])

                msg = chunk.get("message", {})
                model_response += msg.get("content", "")

                if chunk.get("done", False):
                    p_eval = chunk.get("prompt_eval_count", 0)
                    eval_c = chunk.get("eval_count", 0)
                    self.turn_loop.tracker.record_tokens(p_eval, eval_c)

            # Parse repaired code from model response (extract python code blocks if present)
            repaired_code = model_response
            if "```python" in model_response:
                blocks = model_response.split("```python")
                if len(blocks) > 1:
                    repaired_code = blocks[1].split("```")[0].strip()

            # Check Test Weakening Protection: if test_code was modified after iteration 1
            if initial_test_code and current_test_code != initial_test_code:
                test_modified = True
                log.warning("verifier_test_code_modified_warning: model altered test assertions")

            current_code = repaired_code
            iteration += 1

        # Fallback return if loop exits
        end_time_ms = int(asyncio.get_event_loop().time() * 1000)
        return VerifierResult(
            success=False,
            iterations=self.MAX_VERIFIER_ITERATIONS,
            duration_ms=end_time_ms - start_time_ms,
            final_code=current_code,
            final_test_code=current_test_code,
            last_exec_output=last_output or CodeExecOutput(
                run_id="failed", exit_code=-1, stdout_tail=[], stderr_tail=[], duration_ms=0, timed_out=False, output_artifacts=[]
            ),
            test_passed=False,
            test_modified=test_modified,
            ui_label="Verification Failed",
        )
