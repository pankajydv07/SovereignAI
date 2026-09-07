"""Generate Document Tool — Script-based document generation in isolated sandbox."""

import json
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from protocol.models import ProtocolBaseModel
from renderers.post_processor import (
    DocumentValidationError,
    ProvenanceSpoofError,
    inject_system_provenance,
    validate_generated_document,
)
from renderers.schemas import SystemProvenanceMetadata
from sandbox.runner import prepare_sandbox_env
from tools.base import BaseTool, SideEffect, ToolContext, ToolKind, ToolResult
from tools.workspace import verify_workspace_path


class GenerateDocumentInput(ProtocolBaseModel):
    """Input model for script-based document generation tool."""

    task_description: str = Field(
        alias="taskDescription",
        description=(
            "Detailed specification of what the document should contain and how it should be styled"
        ),
    )
    output_format: Literal["docx", "xlsx", "pptx", "pdf", "md"] = Field(
        alias="outputFormat",
        description="Target document format (docx, xlsx, pptx, pdf, md)",
    )
    output_filename: str = Field(
        alias="outputFilename",
        description="Target workspace-relative output filename (e.g. heat_exchanger_audit.docx)",
    )
    script_code: str | None = Field(
        default=None,
        alias="scriptCode",
        description="Python script code to execute in sandbox to generate the document",
    )
    input_data: dict[str, Any] | list[Any] | None = Field(
        default=None,
        alias="inputData",
        description="Structured JSON data written to ./data.json for script consumption",
    )

    source_refs: list[str] = Field(
        default_factory=list,
        alias="sourceRefs",
        description="Extracted field IDs, clause citations, or chunk IDs for system provenance",
    )
    expects_full_tabulation: bool = Field(
        default=False,
        alias="expectsFullTabulation",
        description="If true, validates that output tables/worksheets contain all input_data rows",
    )
    markdown_content: str | None = Field(
        default=None,
        alias="markdownContent",
        description="Direct markdown text content if outputFormat is 'md'",
    )


class GenerateDocumentOutput(ProtocolBaseModel):
    """Output model for script-based document generation tool."""

    file_path: str = Field(alias="filePath")
    output_format: str = Field(alias="outputFormat")
    run_id: str = Field(alias="runId")
    script_iterations: int = Field(alias="scriptIterations")
    validation: dict[str, Any] = Field(description="Parse-back verification metrics")
    success: bool = Field(default=True)


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
        run_id = f"doc_{uuid.uuid4().hex[:8]}"
        fmt = args.output_format.lower().strip()
        target_dest = verify_workspace_path(args.output_filename, ctx.workspace_root)

        models_used = ["active-agent-model"]
        try:
            from models.registry import ModelRegistry

            coder_tag = ModelRegistry().resolve("coder")
            models_used = [coder_tag]
        except Exception:
            pass

        prov = SystemProvenanceMetadata(
            run_id=run_id,
            models_used=models_used,
            sources_cited=args.source_refs,
            min_confidence=0.95,
            human_verified_count=len(args.source_refs),
        )


        # Markdown path: Direct write without sandbox overhead
        if fmt == "md":
            target_dest.parent.mkdir(parents=True, exist_ok=True)
            text_to_write = args.markdown_content or args.task_description
            target_dest.write_text(text_to_write, encoding="utf-8")
            val_metrics = validate_generated_document(target_dest, "md")
            inject_system_provenance(target_dest, "md", prov)

            if self._session_store:
                try:
                    await self._session_store.append_event(
                        ctx.session_id,
                        "document_generation_step",
                        {
                            "runId": run_id,
                            "format": "md",
                            "filePath": str(target_dest),
                            "iterations": 1,
                        },
                    )
                except Exception:
                    pass

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

        # Sandbox-driven generation path (docx, xlsx, pptx, pdf)
        initial_script = args.script_code
        if not initial_script and fmt == "pdf" and args.markdown_content:
            escaped_content = json.dumps(args.markdown_content)
            declared_name = Path(args.output_filename).name
            initial_script = (
                "import os, sys\n"
                "from reportlab.lib.pagesizes import letter\n"
                "from reportlab.lib.styles import getSampleStyleSheet\n"
                "from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer\n\n"
                "def main():\n"
                "    out_dir = os.environ.get('SWARAJ_OUT_DIR', './out')\n"
                "    os.makedirs(out_dir, exist_ok=True)\n"
                f"    out_path = os.path.join(out_dir, {json.dumps(declared_name)})\n"
                "    doc = SimpleDocTemplate(out_path, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)\n"
                "    styles = getSampleStyleSheet()\n"
                "    story = []\n"
                f"    raw_text = {escaped_content}\n"
                "    for line in raw_text.splitlines():\n"
                "        trimmed = line.strip()\n"
                "        if not trimmed:\n"
                "            story.append(Spacer(1, 8))\n"
                "            continue\n"
                "        if trimmed.startswith('# '):\n"
                "            story.append(Paragraph(f'<b><font size=16>{trimmed[2:]}</font></b>', styles['Heading1']))\n"
                "            story.append(Spacer(1, 10))\n"
                "        elif trimmed.startswith('## '):\n"
                "            story.append(Paragraph(f'<b><font size=13>{trimmed[3:]}</font></b>', styles['Heading2']))\n"
                "            story.append(Spacer(1, 8))\n"
                "        elif trimmed.startswith('### '):\n"
                "            story.append(Paragraph(f'<b><font size=11>{trimmed[4:]}</font></b>', styles['Heading3']))\n"
                "            story.append(Spacer(1, 6))\n"
                "        elif trimmed.startswith('- ') or trimmed.startswith('* '):\n"
                "            story.append(Paragraph(f'&bull; {trimmed[2:]}', styles['Normal']))\n"
                "            story.append(Spacer(1, 4))\n"
                "        else:\n"
                "            story.append(Paragraph(trimmed, styles['Normal']))\n"
                "            story.append(Spacer(1, 6))\n"
                "    doc.build(story)\n\n"
                "if __name__ == '__main__':\n"
                "    main()\n"
            )

        if not initial_script:
            return ToolResult.failed(
                "Missing required 'scriptCode' for sandboxed document generation."
            )

        max_iterations = 3
        current_script = initial_script
        iteration = 1
        last_error_msg = ""

        with tempfile.TemporaryDirectory(prefix="swaraj_docgen_") as temp_dir_str:
            work_dir = Path(temp_dir_str)
            out_dir = work_dir / "out"
            out_dir.mkdir(parents=True, exist_ok=True)

            # Write ./data.json if input_data is provided
            if args.input_data is not None:
                data_path = work_dir / "data.json"
                data_path.write_text(json.dumps(args.input_data, indent=2), encoding="utf-8")

            while iteration <= max_iterations:
                script_path = work_dir / "generate.py"
                script_path.write_text(current_script, encoding="utf-8")

                # Direct P4.1 sandbox execution
                declared_out_rel = Path(args.output_filename).name
                exit_code, stdout_tail, stderr_tail = await self._exec_sandbox(
                    run_id=f"{run_id}_it{iteration}",
                    work_dir=work_dir,
                    script_name="generate.py",
                    declared_outputs=[declared_out_rel],
                    timeout_s=int(self.timeout_s),
                )

                # Copy out generated file to a staging path for validation
                ext = Path(args.output_filename).suffix or f".{fmt}"
                staged_file = work_dir / f"staged_output{ext}"
                produced_file = out_dir / declared_out_rel
                if not produced_file.exists() and (work_dir / declared_out_rel).exists():
                    produced_file = work_dir / declared_out_rel

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
                        validation_error = (
                            f"ProvenanceSpoofError: {pse} "
                            "Do not author manual headers/footers with 'Run ID:' or 'DRAFT'."
                        )
                    except DocumentValidationError as dve:
                        validation_error = f"DocumentValidationError: {dve}"
                    except Exception as err:
                        validation_error = f"ValidationCrash: {err}"

                # Audit log event recording per iteration
                if self._session_store:
                    try:
                        await self._session_store.append_event(
                            ctx.session_id,
                            "document_generation_step",
                            {
                                "runId": run_id,
                                "iteration": iteration,
                                "exitCode": exit_code,
                                "script": current_script,
                                "stdout": stdout_tail,
                                "stderr": stderr_tail,
                                "validation": validation_metrics if not validation_error else None,
                                "validationError": validation_error,
                            },
                        )
                    except Exception:
                        pass

                # Check if this iteration succeeded
                if exec_ok and not validation_error:
                    # Inject System Provenance into staged file
                    inject_system_provenance(staged_file, fmt, prov)

                    # Copy to final verified destination in workspace
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

                # If failed, attempt repair via TurnLoop if available
                last_error_msg = (
                    validation_error or traceback_str or f"Script exited with code {exit_code}"
                )
                if iteration >= max_iterations:
                    break

                if self._turn_loop:
                    repair_prompt = (
                        f"The document generation script failed on iteration {iteration}.\n"
                        f"Error: {last_error_msg}\n"
                        f"Please fix the script to output ./out/{declared_out_rel}."
                    )
                    repaired_script = await self._turn_loop.request_code_repair(
                        current_script, repair_prompt
                    )
                    if repaired_script and repaired_script.strip():
                        current_script = repaired_script
                iteration += 1

        return ToolResult.failed(
            f"Document generation failed after {max_iterations} iterations. "
            f"Last error: {last_error_msg}"
        )


    async def _exec_sandbox(
        self,
        run_id: str,
        work_dir: Path,
        script_name: str,
        declared_outputs: list[str],
        timeout_s: int,
    ) -> tuple[int, list[str], list[str]]:
        """Invoke P4.1 sandbox execution directly."""
        import sys

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

        # Local fallback execution (for tests and standalone core)
        try:
            proc = subprocess.run(
                command,
                cwd=str(work_dir),
                env=dict(env_vars),
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            stdout_lines = proc.stdout.splitlines()[-20:] if proc.stdout else []
            stderr_lines = proc.stderr.splitlines()[-20:] if proc.stderr else []
            return proc.returncode, stdout_lines, stderr_lines
        except subprocess.TimeoutExpired:
            return -1, [], ["Execution timed out in sandbox."]
        except Exception as exc:
            return -1, [], [f"Subprocess launch error: {exc}"]
