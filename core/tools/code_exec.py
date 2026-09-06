"""Code Execution Tool — Runs Python code in network-isolated sandbox."""

import os
from pathlib import Path
import tempfile
import time
import uuid
from typing import Any

from pydantic import Field
from protocol.models import ProtocolBaseModel, SandboxExecParams, SandboxExecResult
from sandbox.runner import extract_declared_outputs, prepare_sandbox_env
from tools.base import BaseTool, SideEffect, ToolContext, ToolKind, ToolResult


class CodeExecInput(ProtocolBaseModel):
    """Input model for code execution tool."""

    code: str = Field(description="Python source code implementation to execute")
    test_code: str | None = Field(
        default=None, alias="testCode", description="Optional pytest unit test code to run against the implementation"
    )
    filename: str = Field(default="script.py", description="Filename for target code file")
    timeout_s: float = Field(default=60.0, alias="timeoutS", description="Wall clock execution timeout in seconds")
    declared_outputs: list[str] = Field(
        default_factory=list, alias="declaredOutputs", description="Output artifact file paths relative to out/"
    )


class CodeExecOutput(ProtocolBaseModel):
    """Output model for code execution tool."""

    run_id: str = Field(alias="runId")
    exit_code: int = Field(alias="exitCode")
    stdout_tail: list[str] = Field(default_factory=list, alias="stdoutTail")
    stderr_tail: list[str] = Field(default_factory=list, alias="stderrTail")
    duration_ms: int = Field(alias="durationMs")
    timed_out: bool = Field(alias="timedOut")
    output_artifacts: list[str] = Field(default_factory=list, alias="outputArtifacts")
    test_passed: bool | None = Field(default=None, alias="testPassed")


class CodeExecTool(BaseTool[CodeExecInput, CodeExecOutput]):
    """Tool for running Python scripts in the SWARAJ network-isolated sandbox."""

    name = "code_exec"
    description = "Execute Python code in network-isolated sandbox with optional pytest unit testing"
    kind = ToolKind.EXECUTE
    side_effect = SideEffect.EXEC
    scopes = ["sandbox:exec"]
    timeout_s = 60.0
    is_idempotent = False
    input_model = CodeExecInput
    output_model = CodeExecOutput

    def __init__(self, rpc_runner: Any = None) -> None:
        self._rpc_runner = rpc_runner

    async def run(self, args: CodeExecInput, ctx: ToolContext) -> ToolResult:
        run_id = f"exec_{uuid.uuid4().hex[:8]}"
        start_time = time.monotonic()

        with tempfile.TemporaryDirectory(prefix="swaraj_exec_") as temp_dir_str:
            work_dir = Path(temp_dir_str)
            out_dir = work_dir / "out"
            out_dir.mkdir(parents=True, exist_ok=True)

            # Write code file
            code_file = work_dir / args.filename
            code_file.write_text(args.code, encoding="utf-8")

            # Determine command to run
            if args.test_code:
                test_file = work_dir / "test_runner.py"
                # Combine implementation code and test code cleanly
                full_test_content = f"{args.code}\n\n# --- Pytest Suite ---\n{args.test_code}\n"
                test_file.write_text(full_test_content, encoding="utf-8")
                command = ["python", "-m", "pytest", str(test_file), "-v"]
            else:
                command = ["python", str(code_file)]

            env_vars = prepare_sandbox_env(work_dir)

            # If RPC runner is provided (production), invoke Rust sandbox execution.
            # Otherwise (unit tests / fallback), execute locally in isolated temp directory.
            if self._rpc_runner:
                rpc_params = {
                    "runId": run_id,
                    "command": command,
                    "workDir": str(work_dir.resolve()),
                    "timeoutS": int(args.timeout_s),
                    "env": env_vars,
                    "declaredOutputs": args.declared_outputs,
                }
                raw_res = await self._rpc_runner("sandbox/exec", rpc_params)
                exit_code = raw_res.get("exitCode", -1)
                stdout_tail = raw_res.get("stdoutTail", [])
                stderr_tail = raw_res.get("stderrTail", [])
                duration_ms = raw_res.get("durationMs", int((time.monotonic() - start_time) * 1000))
                timed_out = raw_res.get("timedOut", False)
            else:
                import subprocess

                try:
                    proc = subprocess.run(
                        command,
                        cwd=work_dir,
                        env={**os.environ, **env_vars},
                        stdin=subprocess.DEVNULL,
                        capture_output=True,
                        text=True,
                        timeout=args.timeout_s,
                    )
                    exit_code = proc.returncode
                    stdout_tail = proc.stdout.splitlines()[-200:] if proc.stdout else []
                    stderr_tail = proc.stderr.splitlines()[-200:] if proc.stderr else []
                    duration_ms = int((time.monotonic() - start_time) * 1000)
                    timed_out = False
                except subprocess.TimeoutExpired:
                    exit_code = -1
                    stdout_tail = []
                    stderr_tail = ["Execution timed out"]
                    duration_ms = int(args.timeout_s * 1000)
                    timed_out = True
                except Exception as e:
                    exit_code = -1
                    stdout_tail = []
                    stderr_tail = [str(e)]
                    duration_ms = int((time.monotonic() - start_time) * 1000)
                    timed_out = False

            # Extract declared outputs
            dest_artifacts_dir = ctx.workspace_root / ".swaraj" / "artifacts" / run_id
            output_artifacts = extract_declared_outputs(work_dir, args.declared_outputs, dest_artifacts_dir)

            # Primary truth for test_passed: pytest exit_code == 0 when test_code is provided
            test_passed: bool | None = (exit_code == 0) if args.test_code is not None else None

            output_obj = CodeExecOutput(
                run_id=run_id,
                exit_code=exit_code,
                stdout_tail=stdout_tail,
                stderr_tail=stderr_tail,
                duration_ms=duration_ms,
                timed_out=timed_out,
                output_artifacts=output_artifacts,
                test_passed=test_passed,
            )

            if exit_code == 0 and not timed_out:
                return ToolResult.ok(output_obj.model_dump(by_alias=True))

            err_msg = f"Execution failed with exit code {exit_code}" if not timed_out else "Execution timed out"
            return ToolResult.failed(error=err_msg, output=output_obj.model_dump(by_alias=True))
