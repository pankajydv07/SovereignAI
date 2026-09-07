"""Turn execution runner for dispatching TurnLoop steps and streaming tokens."""

import asyncio
from collections.abc import Callable
import logging
from pathlib import Path
from typing import Any
import uuid

from agent.budget import RunBudget, RunBudgetTracker
from agent.policy import PolicyEngine
from agent.turn_loop import TurnLoop
from storage import SessionStore
from tools.base import ToolContext
from tools.registry import ToolRegistry
from models.ollama import OllamaClient

log = logging.getLogger(__name__)


async def run_chat_turn(
    msg_id: Any,
    session_id: str,
    project_id: str,
    project_path: str | None,
    model_tag: str,
    task_class: str,
    messages: list[dict[str, Any]],
    store: SessionStore,
    ollama: OllamaClient,
    tool_registry: ToolRegistry,
    policy_engine: PolicyEngine,
    request_permission_fn: Callable[..., Any],
    send_notification_fn: Callable[[str, dict[str, Any]], None],
    send_response_fn: Callable[[dict[str, Any]], None],
    log_stderr_fn: Callable[[str], None],
    active_turn_loops: dict[str, TurnLoop],
    active_streams: dict[Any, asyncio.Task[None]],
    success_status: str = "completed",
    extra_result: dict[str, Any] | None = None,
    supports_native_tools: bool = True,
) -> None:
    """Execute a single agent turn loop with streaming tokens and tool status notifications."""
    turn_loop = TurnLoop(
        ollama_client=ollama,
        tool_registry=tool_registry,
        budget_tracker=RunBudgetTracker(budget=RunBudget(max_steps=25, max_run_tokens=128000, wall_clock_timeout_s=300.0)),
        policy_engine=policy_engine,
        permission_requester=request_permission_fn,
        session_store=store,
    )
    active_turn_loops[session_id] = turn_loop
    active_turn_loops[str(msg_id)] = turn_loop
    accumulated_content, accumulated_thinking = "", ""

    async def on_token_callback(delta_cont: str, delta_think: str) -> None:
        nonlocal accumulated_content, accumulated_thinking
        if delta_cont.startswith(("Generated `", "**Executed `")):
            accumulated_content = delta_cont
        else:
            accumulated_content += delta_cont
        accumulated_thinking += delta_think
        send_notification_fn("chat/token", {
            "id": msg_id,
            "sessionId": session_id,
            "model": model_tag,
            "delta": delta_cont,
            "thinking_delta": delta_think,
            "content": accumulated_content,
            "thinking": accumulated_thinking,
        })

    async def on_tool_call_callback(call: dict[str, Any], obs: dict[str, Any] | None) -> None:
        fn_info = call.get("function", {})
        name = fn_info.get("name", "tool")
        send_notification_fn("session/update", {
            "sessionId": session_id,
            "update": {
                "type": "tool_call",
                "toolCall": {
                    "toolCallId": str(uuid.uuid4()),
                    "name": name,
                    "kind": "read" if name.startswith(("fs_read", "kb")) else "edit",
                    "status": "completed" if (obs and obs.get("success", False)) else "failed",
                    "input": fn_info.get("arguments"),
                    "output": obs.get("content") if obs else None,
                },
            },
        })

    try:
        stop_reason, updated_messages = await turn_loop.run_step(
            session_id=session_id,
            model_tag=model_tag,
            messages=messages,
            task_class=task_class,
            supports_native_tools=supports_native_tools,
            tool_context=ToolContext(workspace_root=Path(project_path) if project_path else Path(".")),
            project_id=project_id,
            on_token=on_token_callback,
            on_tool_call=on_tool_call_callback,
        )

        final_content, final_thinking = "", ""
        for m in reversed(updated_messages):
            if m.get("role") == "assistant" and not final_content:
                c = m.get("content", "").strip()
                if c:
                    final_content = c
            if m.get("role") == "assistant" and not final_thinking and m.get("thinking"):
                final_thinking = m.get("thinking", "")
            elif m.get("role") == "tool" and not final_content:
                tool_name = m.get("tool_name", "tool")
                tool_content = m.get("content", "")
                final_content = f"**Executed `{tool_name}`**:\n\n{tool_content}"

        if not final_content and accumulated_content:
            final_content = accumulated_content

        if session_id:
            try:
                await store.append_event(
                    session_id,
                    "message_completed",
                    {"task_class": task_class, "model": model_tag, "content": final_content, "thinking": final_thinking, "stop_reason": stop_reason.value},
                )
            except Exception as err:
                log_stderr_fn(f"Failed to record message_completed: {err}")

        res: dict[str, Any] = {
            "status": success_status,
            "model": model_tag,
            "taskClass": task_class,
            "content": final_content,
            "thinking": final_thinking,
            "stopReason": stop_reason.value,
        }
        if extra_result:
            res.update(extra_result)

        send_response_fn({"jsonrpc": "2.0", "id": msg_id, "result": res})
    except asyncio.CancelledError:
        log_stderr_fn(f"Chat stream id={msg_id} cancelled.")
        send_notification_fn("chat/interrupted", {"id": msg_id, "reason": "cancelled"})
        raise
    except Exception as err:
        log_stderr_fn(f"Chat execution error: {err}")
        send_response_fn({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32002, "message": str(err)}})
    finally:
        active_turn_loops.pop(session_id, None)
        active_turn_loops.pop(str(msg_id), None)
        active_streams.pop(msg_id, None)
