"""SWARAJ Agent Turn Loop, Argument Repair, Budget Tracking, and Policy Approval."""

import asyncio
from collections.abc import Awaitable, Callable
import logging
from pathlib import Path
from typing import Any

from agent.budget import RunBudgetTracker, StopReason
from agent.policy import PolicyEngine
from agent.tool_executor import handle_tool_call
from models.ollama import OllamaApiError, OllamaClient
from tools.base import ToolContext
from tools.registry import ToolRegistry

log = logging.getLogger(__name__)


class TurnLoopError(Exception):
    """Base exception for turn loop failures."""


class RunBudgetExhausted(TurnLoopError):  # noqa: N818
    """Raised when run budget (steps, tokens, wall clock) is exhausted."""

    def __init__(self, stop_reason: StopReason, partial_results: list[dict[str, Any]]) -> None:
        super().__init__(f"Run budget exhausted: {stop_reason.value}")
        self.stop_reason = stop_reason
        self.partial_results = partial_results


class TurnCancelledError(TurnLoopError):
    """Raised when turn execution is cancelled mid-stream by HTTP abort."""

    def __init__(self, partial_results: list[dict[str, Any]]) -> None:
        super().__init__("Turn execution cancelled")
        self.partial_results = partial_results


class TurnLoop:
    """Core turn execution loop managing model stream accumulation, repair, and budgeting."""

    MAX_REPAIR_ATTEMPTS: int = 2

    def __init__(
        self, ollama_client: OllamaClient, tool_registry: ToolRegistry,
        budget_tracker: RunBudgetTracker, policy_engine: PolicyEngine | None = None,
        permission_requester: Callable[[str, str, str, str, str], Awaitable[tuple[str, str | None]]] | None = None,
        session_store: Any | None = None,
    ) -> None:
        self.ollama, self.registry, self.tracker = ollama_client, tool_registry, budget_tracker
        self.policy_engine = policy_engine or PolicyEngine(session_store=session_store)
        self.permission_requester, self.session_store = permission_requester, session_store
        self.active_task: asyncio.Task[Any] | None = None
        self._cancelled: bool = False

    def cancel(self) -> None:
        """Abort in-flight HTTP stream request or tool execution immediately."""
        self._cancelled = True
        if self.active_task and not self.active_task.done():
            self.active_task.cancel()

    async def checkpoint_partial_state(
        self, session_id: str, state: str, details: dict[str, Any]
    ) -> None:
        """Write checkpoint to session store before returning a terminal state."""
        if self.session_store and hasattr(self.session_store, "append_event"):
            try:
                await self.session_store.append_event(
                    session_id=session_id, event_type="checkpoint", payload={"state": state, "details": details}
                )
            except Exception as exc:
                log.warning(f"failed_to_write_checkpoint: {exc}")

    async def run_step(
        self,
        session_id: str,
        model_tag: str,
        messages: list[dict[str, Any]],
        task_class: str = "default",
        required_tool: str | None = None,
        supports_native_tools: bool = True,
        tool_context: ToolContext | None = None,
        project_id: str = "default-project",
        on_token: Callable[[str, str], Awaitable[None]] | None = None,
        on_tool_call: Callable[[dict[str, Any], dict[str, Any] | None], Awaitable[None]] | None = None,
    ) -> tuple[StopReason, list[dict[str, Any]]]:
        """Execute a single turn step with streaming, validation, repair, and budgeting."""
        if self._cancelled:
            await self.checkpoint_partial_state(session_id, "cancelled", {"messages": messages})
            return StopReason.CANCELLED, messages

        stop_reason = self.tracker.get_stop_reason()
        if stop_reason:
            await self.checkpoint_partial_state(session_id, stop_reason.value, {"messages": messages})
            raise RunBudgetExhausted(stop_reason, messages)

        all_tools = self.registry.list_all()
        fallback_path = Path(all_tools[0].name) if all_tools else Path(".")
        ctx = tool_context or ToolContext(workspace_root=fallback_path)

        is_vision = task_class in ("vision_ocr", "vision")
        tools_schema = self.registry.to_ollama_tools(task_class) if (supports_native_tools and not is_vision) else None
        format_param = None
        options = None

        if not supports_native_tools and required_tool:
            tool_obj = self.registry.get(required_tool)
            if tool_obj:
                format_param = tool_obj.input_model.model_json_schema()
                options = {"temperature": 0.0}

        shared_repair_attempts = 0
        repair_checkpoint_index = len(messages)

        sys_prompt = (
            "You are SWARAJ, an air-gapped industrial workbench assistant. "
            "You have direct access to tools to inspect and operate on workspace files:\n"
            "- Use `glob` or `fs_list` to search and find files in the workspace.\n"
            "- Use `fs_read` to read any workspace file (it automatically converts Excel .xlsx/.csv spreadsheets, Word .docx, PPT .pptx, and PDF documents into clean Markdown tables and text).\n"
            "- Use `fs_write` to save output text files.\n"
            "- Use `generate_document` to create and generate `.pdf`, `.docx`, `.xlsx`, and `.md` files directly in the workspace. Whenever the user asks to generate, create, or export a report, summary, document, or PDF, invoke `generate_document` (or `render_deliverable` for official PSU approval notes/memorandums) with `outputFormat` and `outputFilename`. Do not write the generating code in your chat reply.\n"
            "CRITICAL:\n"
            "1. Never state or claim that you cannot open, view, or read binary files, Excel workbooks, or workspace files. Immediately invoke `glob` or `fs_read`.\n"
            "2. Never state or claim that you cannot generate or produce PDF deliverables or documents directly from the workspace. Always call `generate_document` with `outputFormat='pdf'` (or `'docx'`) to create the file directly."
        )

        def get_ollama_messages() -> list[dict[str, Any]]:
            if any(m.get("role") == "system" for m in messages):
                req: list[dict[str, Any]] = []
                for m in messages:
                    if m.get("role") == "system" and "fs_read" not in m.get("content", ""):
                        req.append({**m, "content": f"{m.get('content', '')}\n\n{sys_prompt}"})
                    else:
                        req.append(m)
                return req
            return [{"role": "system", "content": sys_prompt}, *messages]

        while True:
            if self._cancelled:
                await self.checkpoint_partial_state(session_id, "cancelled", {"messages": messages})
                return StopReason.CANCELLED, messages

            self.tracker.record_step()
            rem_time = self.tracker.remaining_time_s()
            if rem_time <= 0.0:
                stop_reason = StopReason.MAX_TOKENS
                await self.checkpoint_partial_state(session_id, stop_reason.value, {"messages": messages})
                raise RunBudgetExhausted(stop_reason, messages)

            try:
                async with asyncio.timeout(rem_time):
                    thinking, content, tool_calls = "", "", []
                    req_msgs = get_ollama_messages()
                    try:
                        async for chunk in self.ollama.stream_chat(
                            model=model_tag, messages=req_msgs, tools=tools_schema,
                            format=format_param, options=options,
                        ):
                            if self._cancelled:
                                await self.checkpoint_partial_state(session_id, "cancelled", {"messages": messages})
                                return StopReason.CANCELLED, messages

                            msg = chunk.get("message", {})
                            raw_think = msg.get("thinking") or ""
                            raw_cont = msg.get("content") or ""
                            d_think = raw_think.encode("utf-8", "replace").decode("utf-8")
                            d_cont = raw_cont.encode("utf-8", "replace").decode("utf-8")
                            thinking += d_think
                            content += d_cont

                            if on_token and (d_cont or d_think):
                                await on_token(d_cont, d_think)

                            if "tool_calls" in msg and msg["tool_calls"]:
                                tool_calls.extend(msg["tool_calls"])

                            if chunk.get("done", False):
                                self.tracker.record_tokens(chunk.get("prompt_eval_count", 0), chunk.get("eval_count", 0))

                    except OllamaApiError as api_err:
                        if "does not support tools" in str(api_err).lower() and tools_schema:
                            tools_schema = None
                            thinking, content, tool_calls = "", "", []
                            async for chunk in self.ollama.stream_chat(
                                model=model_tag, messages=req_msgs, tools=None,
                                format=format_param, options=options,
                            ):
                                msg = chunk.get("message", {})
                                raw_think = msg.get("thinking") or ""
                                raw_cont = msg.get("content") or ""
                                d_think = raw_think.encode("utf-8", "replace").decode("utf-8")
                                d_cont = raw_cont.encode("utf-8", "replace").decode("utf-8")
                                thinking += d_think
                                content += d_cont
                                if on_token and (d_cont or d_think):
                                    await on_token(d_cont, d_think)
                                if chunk.get("done", False):
                                    self.tracker.record_tokens(chunk.get("prompt_eval_count", 0), chunk.get("eval_count", 0))
                        else:
                            raise

            except asyncio.CancelledError:
                self._cancelled = True
                await self.checkpoint_partial_state(session_id, "cancelled", {"messages": messages})
                return StopReason.CANCELLED, messages
            except TimeoutError as exc:
                stop_reason = StopReason.MAX_TOKENS
                await self.checkpoint_partial_state(session_id, stop_reason.value, {"messages": messages})
                raise RunBudgetExhausted(stop_reason, messages) from exc

            assistant_turn: dict[str, Any] = {"role": "assistant", "content": content}
            if thinking:
                assistant_turn["thinking"] = thinking
            if tool_calls:
                assistant_turn["tool_calls"] = tool_calls
            messages.append(assistant_turn)

            if required_tool and not tool_calls and not format_param:
                if shared_repair_attempts < self.MAX_REPAIR_ATTEMPTS:
                    shared_repair_attempts += 1
                    err_msg = f"Step requirement error: Required tool '{required_tool}' was not called. Please invoke the tool."
                    messages.append({"role": "user", "content": err_msg})
                    continue
                break

            if not tool_calls:
                # Intercept model hallucinations claiming it cannot read workspace / binary files
                refusal_markers = (
                    "can't open or read binary",
                    "cannot open or read binary",
                    "can't read binary",
                    "cannot read binary",
                    "sandbox doesn't expose",
                    "sandbox does not expose",
                    "don't have a way to view",
                    "do not have a way to view",
                    "cannot access local files",
                    "can't access local files",
                    "as an ai, i cannot",
                )
                lowered_c = content.lower()
                if any(rm in lowered_c for rm in refusal_markers) and shared_repair_attempts < self.MAX_REPAIR_ATTEMPTS:
                    shared_repair_attempts += 1
                    messages.pop()  # Discard the refusal response
                    err_msg = (
                        "Instruction: You have access to tools. Do not refuse. "
                        "Use `glob` or `fs_list` to search for files, or `fs_read` to read and parse the file into Markdown."
                    )
                    messages.append({"role": "user", "content": err_msg})
                    continue
                break

            tool_errors: list[str] = []
            executed_tools: list[dict[str, Any]] = []

            def on_approval_wait(t_waited: float) -> None:
                self.tracker.start_time += t_waited

            for call in tool_calls:
                obs, err = await handle_tool_call(
                    call=call,
                    session_id=session_id,
                    project_id=project_id,
                    ctx=ctx,
                    registry=self.registry,
                    policy_engine=self.policy_engine,
                    permission_requester=self.permission_requester,
                    session_store=self.session_store,
                    checkpoint_fn=self.checkpoint_partial_state,
                    on_wait_time=on_approval_wait,
                )
                if on_tool_call:
                    await on_tool_call(call, obs)
                if err:
                    tool_errors.append(err)
                elif obs:
                    executed_tools.append(obs)

            if tool_errors:
                if shared_repair_attempts < self.MAX_REPAIR_ATTEMPTS:
                    shared_repair_attempts += 1
                    error_feedback = "\n".join(tool_errors)
                    err_feedback_msg = f"Tool call error feedback: {error_feedback}. Please repair tool arguments and try again."
                    messages.append({"role": "user", "content": err_feedback_msg})
                    continue

            if shared_repair_attempts > 0:
                successful_assistant_turn = messages[-1]
                del messages[repair_checkpoint_index:]
                messages.append(successful_assistant_turn)

            messages.extend(executed_tools)
            shared_repair_attempts = 0
            repair_checkpoint_index = len(messages)
            continue

        return StopReason.END_TURN, messages
