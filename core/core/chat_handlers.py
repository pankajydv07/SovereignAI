"""Chat and Plan execution RPC handlers for SWARAJ Core."""

import asyncio
import base64
import logging
from pathlib import Path
from typing import Any
import uuid

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

from agent.budget import RunBudget, RunBudgetTracker
from agent.planner import PlanStep, Planner
from agent.policy import PolicyDecision, PolicyEngine
from agent.turn_loop import TurnLoop
from models.ollama import OllamaClient
from models.registry import ModelRegistry
from models.router import ModelRouter
from storage import SessionStore
from tools.base import ToolContext
from tools.document_reader import convert_document_to_markdown
from tools.registry import ToolRegistry

log = logging.getLogger(__name__)


class ChatManager:
    """Manages chat streaming, routing, permissions, and plan execution."""

    def __init__(
        self, model_registry: ModelRegistry, tool_registry: ToolRegistry,
        ollama_client: OllamaClient, router: ModelRouter, policy_engine: PolicyEngine,
        send_notification_fn: Any, send_response_fn: Any, log_stderr_fn: Any,
    ) -> None:
        self.model_registry, self.tool_registry = model_registry, tool_registry
        self.ollama, self.router, self.policy_engine = ollama_client, router, policy_engine
        self.send_notification, self.send_response, self.log_stderr = send_notification_fn, send_response_fn, log_stderr_fn
        self.active_streams: dict[Any, asyncio.Task[None]] = {}
        self.active_turn_loops: dict[str, TurnLoop] = {}
        self.active_permission_futures: dict[str, asyncio.Future[tuple[str, str | None]]] = {}

    async def request_permission(
        self, tool: str, side_effect: str, description: str, resource: str, project_id: str
    ) -> tuple[str, str | None]:
        """Emit permission/request and await client decision future."""
        req_id = str(uuid.uuid4())
        fut: asyncio.Future[tuple[str, str | None]] = asyncio.get_running_loop().create_future()
        self.active_permission_futures[req_id] = fut
        self.send_notification("permission/request", {
            "requestId": req_id, "tool": tool, "sideEffect": side_effect,
            "description": description, "resource": resource,
            "options": ["allow_once", "allow_session", "always_allow", "deny"],
        })
        try:
            return await fut
        finally:
            self.active_permission_futures.pop(req_id, None)

    def handle_permission_response(self, req_id: str, option: str, pattern: str | None) -> None:
        """Resolve pending permission future from client permission/respond RPC."""
        if req_id in self.active_permission_futures:
            self.active_permission_futures[req_id].set_result((option, pattern))

    def stop_chat(self, target_id: str) -> None:
        """Cancel active stream or turn loop."""
        if target_id in self.active_turn_loops:
            self.active_turn_loops[target_id].cancel()
        if target_id in self.active_streams:
            self.active_streams[target_id].cancel()

    async def handle_chat_stream(
        self, msg_id: Any, params: dict[str, Any], store: SessionStore
    ) -> None:
        """Stream chat response routed dynamically through ModelRouter and TurnLoop."""
        messages = params.get("messages", [])
        session_id = params.get("sessionId") or str(uuid.uuid4())
        project_id = params.get("projectId", "default-project")
        project_path = params.get("projectPath")
        attachments = params.get("attachments", [])
        plan_first = bool(params.get("planFirst", False))

        user_prompt = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_prompt = m.get("content", "")
                break

        try:
            installed = await self.ollama.get_installed_tags()
        except Exception:
            installed = set(self.model_registry.installed_tags())

        has_image = any(
            isinstance(a, dict)
            and (
                a.get("mime_type", "").startswith("image/")
                or Path(a.get("path") or a.get("name") or a.get("filename") or "").suffix.lower() in IMAGE_EXTENSIONS
            )
            for a in attachments
        )
        mimes = [
            a.get("mime_type") or f"image/{Path(a.get('path', '')).suffix.lower().lstrip('.')}"
            for a in attachments
            if isinstance(a, dict)
            and (
                a.get("mime_type", "").startswith("image/")
                or Path(a.get("path") or a.get("name") or a.get("filename") or "").suffix.lower() in IMAGE_EXTENSIONS
            )
        ]

        decision = self.router.route(prompt=user_prompt, has_image=has_image, mime_types=mimes or None, installed_tags=installed)
        model_tag, task_class = decision.selected_model_tag, decision.task_class
        self.log_stderr(f"Routed '{task_class}' to model '{model_tag}' (conf={decision.confidence:.2f})")

        self.send_notification("chat/routing", {
            "sessionId": session_id,
            "projectId": project_id,
            "prompt": user_prompt,
            "taskClass": task_class,
            "modelTag": model_tag,
            "confidence": decision.confidence,
            "reasoning": f"Routed to {task_class} based on prompt features",
        })

        # Extract and append attachment context and base64 images into messages
        if attachments:
            attachment_contexts: list[str] = []
            attached_images: list[str] = []
            for att in attachments:
                if not isinstance(att, dict):
                    continue
                att_name = att.get("name") or att.get("filename") or "Attachment"
                att_path = att.get("path")
                att_content = att.get("content")
                if att_path:
                    p = Path(att_path)
                    if p.exists() and p.is_file():
                        suf = p.suffix.lower()
                        if suf in IMAGE_EXTENSIONS:
                            try:
                                b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
                                attached_images.append(b64)
                                attachment_contexts.append(f"### Attached Image: {att_name} ({p.name})")
                            except Exception as e:
                                attachment_contexts.append(f"### Attached Image: {att_name} (Failed to load: {e})")
                        else:
                            try:
                                doc_md = convert_document_to_markdown(p)
                                clean_md = doc_md.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
                                attachment_contexts.append(f"### Document: {att_name} ({p.name})\n\n{clean_md[:32000]}")
                            except Exception as e:
                                attachment_contexts.append(f"### Document: {att_name} (Failed to read: {e})")
                elif att_content:
                    clean_att = str(att_content).encode("utf-8", errors="replace").decode("utf-8", errors="replace")
                    attachment_contexts.append(f"### Document: {att_name}\n```\n{clean_att[:24000]}\n```")

            if attachment_contexts or attached_images:
                combined_context = (
                    "The user has provided the following attached context:\n\n" + "\n\n".join(attachment_contexts)
                ) if attachment_contexts else ""
                if messages and messages[-1].get("role") == "user":
                    if combined_context:
                        messages[-1]["content"] = f"{combined_context}\n\n---\nUser Query: {messages[-1].get('content', '')}"
                    if attached_images:
                        messages[-1]["images"] = attached_images
                else:
                    msg_obj: dict[str, Any] = {"role": "user", "content": combined_context or user_prompt}
                    if attached_images:
                        msg_obj["images"] = attached_images
                    messages.append(msg_obj)

        if session_id:
            try:
                first_line = user_prompt.strip().split("\n")[0][:48]
                clean_title = first_line if first_line else f"Chat {session_id[:8]}"
                try:
                    s_obj = await store.get_session(session_id)
                    cur_title = s_obj.get("title", "")
                    if cur_title.startswith(("Session ", "Chat ")):
                        await store.update_session_title(session_id, clean_title)
                except Exception:
                    await store.create_session(session_id, project_id, clean_title)
                await store.append_event(session_id, "message_started", {"task_class": task_class, "model": model_tag, "messages": messages})
            except Exception as err:
                self.log_stderr(f"Failed to record message_started: {err}")

        is_plan_path = plan_first or (task_class in ("official_drafting", "engineering_calc") and not attachments)
        if is_plan_path:
            self.log_stderr(f"Entering Plan Path for task class '{task_class}'")
            planner = Planner(self.ollama)
            try:
                plan_prompt = messages[-1].get("content", "") if (messages and messages[-1].get("role") == "user") else user_prompt
                steps = await planner.generate_plan(plan_prompt, model_tag, task_class=task_class)
                raw_steps = [s.model_dump(by_alias=True) for s in steps]
                self.send_notification("session/update", {"sessionId": session_id, "update": {"type": "plan", "steps": raw_steps}})
                if session_id:
                    try:
                        await store.append_event(session_id, "plan_created", {"steps": raw_steps})
                    except Exception as err:
                        self.log_stderr(f"Failed to record plan_created event: {err}")
                self.send_response({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"status": "plan_created", "model": model_tag, "taskClass": task_class, "steps": raw_steps},
                })
                return
            except Exception as exc:
                self.log_stderr(f"Planner failed: {exc}, falling back to direct execution")

        turn_loop = TurnLoop(
            ollama_client=self.ollama,
            tool_registry=self.tool_registry,
            budget_tracker=RunBudgetTracker(budget=RunBudget(max_steps=25, max_run_tokens=128000, wall_clock_timeout_s=300.0)),
            policy_engine=self.policy_engine,
            permission_requester=self.request_permission,
            session_store=store,
        )
        self.active_turn_loops[session_id] = turn_loop
        self.active_turn_loops[str(msg_id)] = turn_loop
        accumulated_content, accumulated_thinking = "", ""

        async def on_token_callback(delta_cont: str, delta_think: str) -> None:
            nonlocal accumulated_content, accumulated_thinking
            accumulated_content += delta_cont
            accumulated_thinking += delta_think
            self.send_notification("chat/token", {
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
            self.send_notification("session/update", {
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
                tool_context=ToolContext(workspace_root=Path(project_path) if project_path else Path(".")),
                project_id=project_id,
                on_token=on_token_callback,
                on_tool_call=on_tool_call_callback,
            )

            final_content, final_thinking = "", ""
            for m in reversed(updated_messages):
                if m.get("role") == "assistant":
                    if not final_content and m.get("content"):
                        final_content = m.get("content", "")
                    if not final_thinking and m.get("thinking"):
                        final_thinking = m.get("thinking", "")
                elif m.get("role") == "tool" and not final_content:
                    tool_name = m.get("tool_name", "tool")
                    tool_content = m.get("content", "")
                    final_content = f"**Executed `{tool_name}`**:\n\n{tool_content}"

            if session_id:
                try:
                    await store.append_event(
                        session_id,
                        "message_completed",
                        {"task_class": task_class, "model": model_tag, "content": final_content, "thinking": final_thinking, "stop_reason": stop_reason.value},
                    )
                except Exception as err:
                    self.log_stderr(f"Failed to record message_completed: {err}")

            self.send_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"status": "completed", "model": model_tag, "taskClass": task_class, "content": final_content, "thinking": final_thinking, "stopReason": stop_reason.value},
            })
        except asyncio.CancelledError:
            self.log_stderr(f"Chat stream id={msg_id} cancelled.")
            self.send_notification("chat/interrupted", {"id": msg_id, "reason": "cancelled"})
            raise
        except Exception as err:
            self.log_stderr(f"Chat execution error: {err}")
            self.send_response({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32002, "message": str(err)}})
        finally:
            self.active_turn_loops.pop(session_id, None)
            self.active_turn_loops.pop(str(msg_id), None)
            self.active_streams.pop(msg_id, None)

    async def handle_plan_run(
        self, msg_id: Any, params: dict[str, Any], store: SessionStore
    ) -> None:
        """Execute structured plan steps sequentially with dependency and policy checks."""
        session_id = params.get("sessionId") or str(uuid.uuid4())
        project_id = params.get("projectId", "default-project")
        raw_steps = params.get("steps", [])

        try:
            steps = [PlanStep.model_validate(s) for s in raw_steps]
        except Exception as exc:
            self.send_response({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32602, "message": f"Invalid plan steps: {exc}"}})
            return

        budget_tracker = RunBudgetTracker(budget=RunBudget(max_steps=len(steps) + 5, max_run_tokens=128000, wall_clock_timeout_s=300.0))
        turn_loop = TurnLoop(
            ollama_client=self.ollama,
            tool_registry=self.tool_registry,
            budget_tracker=budget_tracker,
            policy_engine=self.policy_engine,
            permission_requester=self.request_permission,
            session_store=store,
        )
        self.active_turn_loops[session_id] = turn_loop
        completed_indices: set[int] = set()
        step_results: list[dict[str, Any]] = []

        for step in steps:
            missing_deps = [dep for dep in step.dependencies if dep not in completed_indices]
            if missing_deps:
                err_msg = f"Step {step.step_index} blocked on missing dependencies: {missing_deps}"
                step_results.append({"stepIndex": step.step_index, "status": "failed", "error": err_msg})
                break

            self.send_notification("session/update", {
                "sessionId": session_id,
                "update": {
                    "type": "plan",
                    "steps": [{**s.model_dump(by_alias=True), "status": "running"} if s.step_index == step.step_index else s.model_dump(by_alias=True) for s in steps],
                },
            })

            tool_name = step.tool or "fs_read"
            tool_inst = self.tool_registry.get(tool_name)
            if not tool_inst:
                err_msg = f"Unknown tool '{tool_name}' for step {step.step_index}"
                step_results.append({"stepIndex": step.step_index, "status": "failed", "error": err_msg})
                break

            res_str = step.description[:40] if step.description else "<plan_step_resource>"
            decision, matched_pat = await self.policy_engine.decide(
                subject=None,
                tool=tool_name,
                resource=res_str,
                side_effect=tool_inst.side_effect,
                project_id=project_id,
            )

            if decision == PolicyDecision.DENY:
                step_results.append({"stepIndex": step.step_index, "status": "failed", "error": f"Denied by policy: {matched_pat}"})
                break

            if decision == PolicyDecision.ASK:
                choice, pat = await self.request_permission(tool_name, tool_inst.side_effect.value, step.description, res_str, project_id)
                if choice not in ("allow_once", "allow_session", "always_allow"):
                    step_results.append({"stepIndex": step.step_index, "status": "failed", "error": "Permission denied by user"})
                    break
                if choice == "allow_session":
                    self.policy_engine.add_session_rule(project_id, tool_name, pat or "**")

            completed_indices.add(step.step_index)
            step_results.append({"stepIndex": step.step_index, "status": "completed"})

        self.active_turn_loops.pop(session_id, None)
        self.send_response({"jsonrpc": "2.0", "id": msg_id, "result": {"status": "plan_executed", "results": step_results}})
