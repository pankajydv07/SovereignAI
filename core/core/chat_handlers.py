"""Chat and Plan execution RPC handlers for SWARAJ Core."""

import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import inspect
import logging
from pathlib import Path
from typing import Any
import uuid

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

from agent.planner import PlanStep, Planner
from agent.policy import PolicyEngine
from core.attachment_loader import extract_attachment_features, process_chat_attachments
from core.pre_retrieval import maybe_execute_preretrieval
from core.turn_runner import run_chat_turn
from kb.attachment_index import AttachmentIndexRequest, AttachmentIndexService
from kb.store import KnowledgeBaseStore
from kb.types import ClassificationLevel
from models.ollama import OllamaClient
from models.registry import ModelRegistry
from models.router import ModelRouter
from storage import SessionStore
from tools.registry import ToolRegistry

log = logging.getLogger(__name__)


class ChatManager:
    """Manages chat streaming, routing, permissions, and plan execution."""

    def __init__(
        self,
        model_registry: ModelRegistry,
        tool_registry: ToolRegistry,
        ollama_client: OllamaClient,
        router: ModelRouter,
        policy_engine: PolicyEngine,
        send_notification_fn: Any,
        send_response_fn: Any,
        log_stderr_fn: Any,
        attachment_index_service: AttachmentIndexService | None = None,
    ) -> None:
        self.model_registry = model_registry
        self.tool_registry = tool_registry
        self.ollama = ollama_client
        self.router = router
        self.policy_engine = policy_engine
        self.send_notification = send_notification_fn
        self.send_response = send_response_fn
        self.log_stderr = log_stderr_fn
        self.attachment_index_service = attachment_index_service
        self.active_streams: dict[Any, asyncio.Task[None]] = {}
        self.active_turn_loops: dict[str, TurnLoop] = {}
        self.active_permission_futures: dict[str, asyncio.Future[tuple[str, str | None]]] = {}
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self.active_indexing_tasks: dict[str, list[asyncio.Task[Any]]] = {}

    def _get_attachment_index_service(self, store: SessionStore) -> AttachmentIndexService:
        if self.attachment_index_service:
            return self.attachment_index_service
        kb_store = KnowledgeBaseStore(store.db_manager)
        return AttachmentIndexService(kb_store=kb_store, send_notification_fn=self.send_notification)

    def _emit_failure_if_raised(self, task: asyncio.Task[Any], session_id: str, doc_id: str) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            self.log_stderr(f"Background attachment indexing error: {exc}")
            self.send_notification("session/update", {
                "sessionId": session_id,
                "update": {
                    "type": "attachment_index_failed",
                    "documentId": doc_id,
                    "reason": str(exc),
                    "directReadSucceeded": True,
                },
            })

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
        """Cancel active stream, turn loop, and background indexing tasks."""
        if target_id in self.active_turn_loops:
            self.active_turn_loops[target_id].cancel()
        if target_id in self.active_streams:
            self.active_streams[target_id].cancel()
        if isinstance(target_id, str) and target_id.lstrip("-").isdigit():
            int_id = int(target_id)
            if int_id in self.active_streams:
                self.active_streams[int_id].cancel()
            if int_id in self.active_turn_loops:
                self.active_turn_loops[int_id].cancel()
        if target_id in self.active_indexing_tasks:
            tasks = self.active_indexing_tasks.pop(target_id, [])
            for task in tasks:
                if not task.done():
                    task.cancel()

    def _spawn_attachment_indexing(
        self,
        attachments: list[dict[str, Any]],
        project_id: str,
        session_id: str,
        user_id: str,
        store: SessionStore,
        uploaded_at: str | None = None,
    ) -> None:
        """Spawn asynchronous background indexing tasks for PDF attachments."""
        service = self._get_attachment_index_service(store)
        for att in attachments:
            if not isinstance(att, dict):
                continue
            att_path_str = att.get("path")
            if not att_path_str:
                continue
            p = Path(att_path_str)
            if p.suffix.lower() == ".pdf" and p.exists() and p.is_file():
                try:
                    file_bytes = p.read_bytes()
                    sha256_hash = hashlib.sha256(file_bytes).hexdigest()
                    doc_id = f"doc_{project_id}_{sha256_hash[:12]}"
                    req = AttachmentIndexRequest(
                        project_id=project_id,
                        session_id=session_id,
                        source_path=str(p.resolve()),
                        original_filename=att.get("name") or att.get("filename") or p.name,
                        sha256=sha256_hash,
                        mime_type="application/pdf",
                        size_bytes=len(file_bytes),
                        uploaded_at=uploaded_at or datetime.now(timezone.utc).isoformat(),
                        uploader_id=user_id,
                        classification=ClassificationLevel.CONFIDENTIAL,
                        source_kind="chat_attachment",
                        scope="project",
                    )
                    task = asyncio.create_task(service.index_attachment(req))
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)
                    task.add_done_callback(lambda t, s=session_id, d=doc_id: self._emit_failure_if_raised(t, s, d))
                    self.active_indexing_tasks.setdefault(session_id, []).append(task)
                except Exception as err:
                    self.log_stderr(f"Failed to initiate attachment indexing for {p.name}: {err}")

    async def _check_model_supports_tools(self, model_tag: str) -> bool:
        """Check if model supports native tool calling via discovery with yaml override."""
        yaml_overrides = self.model_registry.get_overrides(model_tag)
        if "supports_native_tools" in yaml_overrides:
            return bool(yaml_overrides["supports_native_tools"])
        check_fn = getattr(self.ollama, "check_supports_tools", None)
        if callable(check_fn):
            res = check_fn(model_tag)
            return await res if inspect.isawaitable(res) else bool(res)
        return False

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
        rag_mode = bool(params.get("ragMode", False))

        user_prompt = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_prompt = m.get("content", "")
                break

        try:
            installed = await self.ollama.get_installed_tags()
        except Exception:
            installed = set(self.model_registry.installed_tags())

        has_image, mimes = extract_attachment_features(attachments)

        try:
            decision = await self.router.route(
                prompt=user_prompt,
                has_image=has_image,
                mime_types=mimes or None,
                installed_tags=installed,
            )
        except Exception as exc:
            err_msg = str(exc)
            self.log_stderr(f"Routing error: {err_msg}")
            self.send_notification("chat/token", {
                "id": msg_id, "sessionId": session_id, "model": "router",
                "delta": err_msg, "thinking_delta": "", "content": err_msg, "thinking": "",
            })
            self.send_response({
                "jsonrpc": "2.0", "id": msg_id,
                "result": {"status": "completed", "model": "router", "taskClass": "other", "content": err_msg, "thinking": "", "stopReason": "end_turn"},
            })
            return

        model_tag, task_class = decision.selected_model_tag, decision.task_class
        if rag_mode and task_class == "other":
            task_class = "kb_qa"
        self.log_stderr(f"Routed '{task_class}' to model '{model_tag}' (conf={decision.confidence:.2f}, band={decision.confidence_band}, ragMode={rag_mode})")

        self.send_notification("chat/routing", {
            "sessionId": session_id,
            "projectId": project_id,
            "prompt": user_prompt,
            "taskClass": task_class,
            "modelTag": model_tag,
            "confidence": decision.confidence,
            "confidenceBand": decision.confidence_band,
            "reasoning": f"Routed to {task_class} (ragMode={rag_mode})",
        })

        # Discover tool support capability from Ollama / models.yaml
        supports_native_tools = await self._check_model_supports_tools(model_tag)

        # Spawn asynchronous background indexing for PDF attachments
        self._spawn_attachment_indexing(
            attachments=attachments,
            project_id=project_id,
            session_id=session_id,
            user_id=str(params.get("userId") or params.get("userRole") or "InspectionEngineer"),
            store=store,
            uploaded_at=params.get("uploadedAt"),
        )

        # Conditional Pre-Retrieval gated on task_class or explicit ragMode
        num_ctx = self.model_registry.get_num_ctx(model_tag)
        await maybe_execute_preretrieval(
            task_class=task_class,
            user_prompt=user_prompt,
            user_role=str(params.get("userRole") or "InspectionEngineer"),
            num_ctx=num_ctx,
            model_registry=self.model_registry,
            session_store=store,
            session_id=session_id,
            messages=messages,
            send_notification_fn=self.send_notification,
            query_vector=decision.prompt_embedding,
            force_retrieval=rag_mode,
        )

        # Dynamic budget for direct parse attachments (remaining context after pre-retrieval)
        remaining_budget = max(2000, num_ctx - 4000)
        process_chat_attachments(attachments, messages, user_prompt, max_context_tokens=remaining_budget)

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

        is_plan_path = plan_first
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

        await run_chat_turn(
            msg_id=msg_id,
            session_id=session_id,
            project_id=project_id,
            project_path=project_path,
            model_tag=model_tag,
            task_class=task_class,
            messages=messages,
            store=store,
            ollama=self.ollama,
            tool_registry=self.tool_registry,
            policy_engine=self.policy_engine,
            request_permission_fn=self.request_permission,
            send_notification_fn=self.send_notification,
            send_response_fn=self.send_response,
            log_stderr_fn=self.log_stderr,
            active_turn_loops=self.active_turn_loops,
            active_streams=self.active_streams,
            success_status="completed",
            supports_native_tools=supports_native_tools,
        )

    async def handle_plan_run(
        self, msg_id: Any, params: dict[str, Any], store: SessionStore
    ) -> None:
        """Execute structured plan steps via Agent TurnLoop and streaming updates."""
        session_id = params.get("sessionId") or str(uuid.uuid4())
        project_id = params.get("projectId", "default-project")
        project_path = params.get("projectPath")
        raw_steps = params.get("steps", [])

        try:
            steps = [PlanStep.model_validate(s) for s in raw_steps]
        except Exception as exc:
            self.send_response({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32602, "message": f"Invalid plan steps: {exc}"}})
            return

        plan_summary = "\n".join(f"Step {s.step_index}: {s.description}" for s in steps)
        plan_exec_prompt = (
            f"Please execute the following approved execution plan step-by-step and produce the final deliverables:\n\n"
            f"{plan_summary}"
        )

        messages = [{"role": "user", "content": plan_exec_prompt}]

        try:
            installed = await self.ollama.get_installed_tags()
        except Exception:
            installed = set(self.model_registry.installed_tags())

        decision = await self.router.route(prompt=plan_exec_prompt, installed_tags=installed)
        model_tag, task_class = decision.selected_model_tag, decision.task_class
        extra_result = {"results": [{"stepIndex": s.step_index, "status": "completed"} for s in steps]}
        supports_tools = await self._check_model_supports_tools(model_tag)

        await run_chat_turn(
            msg_id=msg_id,
            session_id=session_id,
            project_id=project_id,
            project_path=project_path,
            model_tag=model_tag,
            task_class=task_class,
            messages=messages,
            store=store,
            ollama=self.ollama,
            tool_registry=self.tool_registry,
            policy_engine=self.policy_engine,
            request_permission_fn=self.request_permission,
            send_notification_fn=self.send_notification,
            send_response_fn=self.send_response,
            log_stderr_fn=self.log_stderr,
            active_turn_loops=self.active_turn_loops,
            active_streams=self.active_streams,
            success_status="plan_executed",
            extra_result=extra_result,
            supports_native_tools=supports_tools,
        )

