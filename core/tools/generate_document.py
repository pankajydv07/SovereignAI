"""Generate Document Tool — Script-based document generation in isolated sandbox."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Literal
import uuid

import structlog
from pydantic import Field

from protocol.models import ProtocolBaseModel
from renderers.governance import check_official_deliverable_boundary
from renderers.post_processor import (
    DocumentValidationError,
    ProvenanceSpoofError,
    inject_system_provenance,
    validate_generated_document,
)
from renderers.schemas import SystemProvenanceMetadata
from sandbox.runner import prepare_sandbox_env
from tools.base import BaseTool, SideEffect, ToolContext, ToolKind, ToolResult
from tools.doc_script_builder import (
    build_docx_script,
    build_pdf_script,
    build_pptx_script,
    build_xlsx_script,
    normalize_typographic_punctuation,
)
from tools.workspace import verify_workspace_path

log = structlog.get_logger()


class SandboxUnavailableError(RuntimeError):
    """Raised when the sandbox RPC execution encounters an unrecoverable failure."""


class GenerateDocumentInput(ProtocolBaseModel):
    """Input model for script-based document generation tool."""

    task_description: str = Field(
        alias="taskDescription",
        description="Detailed specification of what the document should contain and how it should be styled",
    )
    output_format: Literal["docx", "xlsx", "pptx", "pdf", "md"] = Field(
        alias="outputFormat", description="Target document format (docx, xlsx, pptx, pdf, md)"
    )
    output_filename: str = Field(
        alias="outputFilename",
        description="Target workspace-relative output filename (e.g. heat_exchanger_audit.pdf)",
    )
    script_code: str | None = Field(
        default=None,
        alias="scriptCode",
        description="Python script code to execute in sandbox to generate the document",
    )
    input_data: dict[str, Any] | list[Any] | None = Field(
        default=None, alias="inputData", description="Structured JSON data written to ./data.json"
    )
    source_refs: list[str] = Field(
        default_factory=list, alias="sourceRefs", description="Extracted field IDs or citations"
    )
    expects_full_tabulation: bool = Field(
        default=False,
        alias="expectsFullTabulation",
        description="Validate that output contains all input_data rows",
    )
    markdown_content: str | None = Field(
        default=None, alias="markdownContent", description="Markdown text content"
    )


class GenerateDocumentOutput(ProtocolBaseModel):
    """Output model for script-based document generation tool."""

    file_path: str = Field(alias="filePath", description="Workspace-relative path to produced file")
    output_format: str = Field(alias="outputFormat", description="File extension / format")
    run_id: str = Field(alias="runId", description="Unique identifier for the document execution")
    script_iterations: int = Field(
        alias="scriptIterations", description="Number of sandbox repair iterations executed"
    )
    validation: dict[str, Any] = Field(
        default_factory=dict, description="Structural and cardinality validation metrics"
    )
    success: bool = Field(default=True, description="Whether document generation succeeded")


class GenerateDocumentTool(BaseTool[GenerateDocumentInput, GenerateDocumentOutput]):
    """Tool for script-driven document generation (.docx, .xlsx, .pptx, .pdf) in sandbox."""

    name = "generate_document"
    description = (
        "Generate custom documents (.docx, .xlsx, .pptx, .pdf, .md) "
        "by executing sandboxed Python scripts"
    )
    kind = ToolKind.OTHER
    side_effect = SideEffect.WRITE
    scopes = ["workspace:write", "sandbox:exec"]
    timeout_s = 120.0
    is_idempotent = False
    input_model = GenerateDocumentInput
    output_model = GenerateDocumentOutput

    def __init__(
        self,
        rpc_runner: Any | None = None,
        turn_loop: Any | None = None,
        session_store: Any | None = None,
    ) -> None:
        self._rpc_runner = rpc_runner
        self._turn_loop = turn_loop
        self._session_store = session_store

    async def run(self, args: GenerateDocumentInput, ctx: ToolContext) -> ToolResult:
        target_dest = verify_workspace_path(args.output_filename, ctx.workspace_root)
        fmt = args.output_format.lower().strip()

        check_official_deliverable_boundary(
            args.output_filename, args.task_description, args.script_code
        )
        run_id = f"doc_{uuid.uuid4().hex[:8]}"

        models_used = ["active-agent-model"]
        try:
            from models.registry import ModelRegistry

            coder_tag = ModelRegistry().resolve("coder")
            models_used = [coder_tag]
        except Exception as exc: # allowed-silent
            log.warning("coder_model_resolve_failed", error=str(exc))

        prov = SystemProvenanceMetadata(
            run_id=run_id,
            models_used=models_used,
            sources_cited=args.source_refs,
            min_confidence=0.95,
            human_verified_count=len(args.source_refs),
        )

        # Markdown direct path
        if fmt == "md":
            target_dest.parent.mkdir(parents=True, exist_ok=True)
            text_to_write = normalize_typographic_punctuation(args.markdown_content or args.task_description)
            target_dest.write_text(text_to_write, encoding="utf-8")
            val_metrics = validate_generated_document(target_dest, "md")
            inject_system_provenance(target_dest, "md", prov)
            return ToolResult.ok(
                GenerateDocumentOutput(
                    filePath=str(target_dest.resolve()),
                    outputFormat="md",
                    runId=run_id,
                    scriptIterations=1,
                    validation=val_metrics,
                    success=True,
                )
            )

        # Build initial script if not provided
        initial_script = args.script_code
        declared_name = Path(args.output_filename).name
        content = normalize_typographic_punctuation(args.markdown_content or args.task_description)

        if not initial_script and fmt == "pdf" and content:
            initial_script = build_pdf_script(declared_name, content)
        elif not initial_script and fmt == "docx" and content:
            initial_script = build_docx_script(declared_name, content)
        elif not initial_script and fmt == "pptx" and content:
            initial_script = build_pptx_script(declared_name, content)
        elif not initial_script and fmt == "xlsx" and content:
            initial_script = build_xlsx_script(declared_name, content)

        if not initial_script:
            return ToolResult.failed("Missing required 'scriptCode' or content for document generation.")

        max_iterations = 3
        current_script = initial_script
        iteration = 1
        last_error_msg = ""

        with tempfile.TemporaryDirectory(prefix="swaraj_docgen_") as temp_dir_str:
            work_dir = Path(temp_dir_str)
            out_dir = work_dir / "out"
            out_dir.mkdir(parents=True, exist_ok=True)

            if args.input_data is not None:
                data_path = work_dir / "data.json"
                data_path.write_text(json.dumps(args.input_data, indent=2), encoding="utf-8")

            while iteration <= max_iterations:
                script_path = work_dir / "generate.py"
                script_path.write_text(current_script, encoding="utf-8")

                exit_code, stdout_tail, stderr_tail = await self._exec_sandbox(
                    run_id=f"{run_id}_it{iteration}",
                    work_dir=work_dir,
                    script_name="generate.py",
                    declared_outputs=[declared_name],
                    timeout_s=int(self.timeout_s),
                )

                ext = Path(args.output_filename).suffix or f".{fmt}"
                staged_file = work_dir / f"staged_output{ext}"
                produced_file = out_dir / declared_name
                if not produced_file.exists() and (work_dir / declared_name).exists():
                    produced_file = work_dir / declared_name

                exec_ok = (exit_code == 0) and produced_file.exists()
                traceback_str = "\n".join(stderr_tail) if stderr_tail else None
                validation_metrics: dict[str, Any] = {}
                validation_error: str | None = None

                if exec_ok:
                    shutil.copy2(produced_file, staged_file)
                    try:
                        validation_metrics = validate_generated_document(
                            file_path=staged_file,
                            output_format=fmt,
                            input_data=args.input_data,
                            expects_full_tabulation=args.expects_full_tabulation,
                        )
                    except ProvenanceSpoofError as pse:
                        validation_error = f"ProvenanceSpoofError: {pse}"
                    except DocumentValidationError as dve:
                        validation_error = f"DocumentValidationError: {dve}"
                    except Exception as err:  # allowed-silent
                        validation_error = f"ValidationCrash: {err}"

                if self._session_store:
                    try:
                        await self._session_store.append_event(
                            ctx.session_id,
                            "document_generation_step",
                            {
                                "runId": run_id,
                                "iteration": iteration,
                                "exitCode": exit_code,
                                "declaredOutputs": [declared_name],
                            },
                        )
                    except Exception as exc:  # allowed-silent
                        log.warning("append_event_failed", session_id=ctx.session_id, error=str(exc))

                if exec_ok and not validation_error:
                    inject_system_provenance(staged_file, fmt, prov)
                    target_dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(staged_file, target_dest)

                    return ToolResult.ok(
                        GenerateDocumentOutput(
                            filePath=str(target_dest.resolve()),
                            outputFormat=fmt,
                            runId=run_id,
                            scriptIterations=iteration,
                            validation=validation_metrics,
                            success=True,
                        )
                    )

                last_error_msg = validation_error or traceback_str or f"Script exited with code {exit_code}"
                if iteration >= max_iterations:
                    break

                if self._turn_loop:
                    repair_prompt = (
                        f"The document generation script failed on iteration {iteration}.\n"
                        f"Error: {last_error_msg}\n"
                        f"Please fix the script to output ./out/{declared_name}."
                    )
                    repaired = await self._turn_loop.request_code_repair(current_script, repair_prompt)
                    if repaired and repaired.strip():
                        current_script = repaired
                iteration += 1

        return ToolResult.failed(
            f"Document generation failed after {max_iterations} iterations. Last error: {last_error_msg}"
        )

    async def _exec_sandbox(
        self,
        run_id: str,
        work_dir: Path,
        script_name: str,
        declared_outputs: list[str],
        timeout_s: int,
    ) -> tuple[int, list[str], list[str]]:
        """Invoke sandbox execution via supervisor RPC or isolated subprocess with sandbox env."""
        env_vars = prepare_sandbox_env(work_dir)
        command = [sys.executable, script_name]

        if self._rpc_runner:
            rpc_params = {
                "runId": run_id,
                "command": command,
                "workDir": str(work_dir.resolve()),
                "timeoutS": timeout_s,
                "env": env_vars,
                "declaredOutputs": declared_outputs,
            }
            raw_res = await self._rpc_runner("sandbox/exec", rpc_params)
            return (
                raw_res.get("exitCode", -1),
                raw_res.get("stdoutTail", []),
                raw_res.get("stderrTail", []),
            )

        try:
            proc = subprocess.run(
                command,
                cwd=work_dir,
                env={**os.environ, **env_vars},
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            return (
                proc.returncode,
                proc.stdout.splitlines()[-200:] if proc.stdout else [],
                proc.stderr.splitlines()[-200:] if proc.stderr else [],
            )
        except subprocess.TimeoutExpired:
            return (-1, [], ["Execution timed out"])
        except Exception as exc: # allowed-silent
            return (-1, [], [str(exc)])
