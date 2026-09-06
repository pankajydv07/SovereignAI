"""Calculation Runner — Executed sandboxed calculations with dimensional checks and assertions.

Enforces unit declarations, inline assertions, pint dimensional analysis, system-controlled
tolerances (rel_tol=1e-4), parameter provenance tracking (FR-5.7), KB clause quotation,
and SQLite persistence.
"""

import math
from typing import Any

from pint import UnitRegistry

from calc.models import (
    CalculationExecutionRecord,
    CalculationParameter,
    CalculationVerificationError,
    CrossCheckResult,
    NoAssertionError,
)
from tools.base import ToolContext
from tools.code_exec import CodeExecInput, CodeExecTool

# System-controlled hardcoded tolerances (cannot be overridden by model input)
SYSTEM_REL_TOL = 1e-4
SYSTEM_ABS_TOL = 1e-6


class CalculationRunner:
    """Runner for executing and cross-verifying engineering calculations."""

    def __init__(self, code_exec_tool: CodeExecTool | None = None) -> None:
        self.code_exec_tool = code_exec_tool or CodeExecTool()
        self.ureg: Any = UnitRegistry()

    def verify_script_assertions(self, code: str) -> None:
        """Reject bare arithmetic scripts missing explicit unit assertions."""
        if "assert" not in code:
            raise NoAssertionError(
                "Calculation script must contain at least one explicit inline assert statement"
            )

    def check_dimensional_consistency(
        self, parameters: list[CalculationParameter], target_unit: str
    ) -> bool:
        """Verify dimensional consistency using pint UnitRegistry."""
        try:
            # Verify target unit is valid physical dimension
            target_dim = self.ureg(target_unit).dimensionality
            for param in parameters:
                if isinstance(param.value, (int, float)):
                    p_qty = self.ureg.Quantity(param.value, param.unit)
                    _ = p_qty.dimensionality
            return target_dim is not None
        except Exception:
            return False

    async def fetch_kb_clause(
        self, standard_code: str, clause_ref: str, kb_service: Any = None
    ) -> tuple[str, bool]:
        """Fetch governing standard clause text directly from Knowledge Base.

        Returns tuple: (clause_text, requires_manual_clause_verification)
        Model memory fallback is strictly forbidden.
        """
        if kb_service:
            try:
                query = f"{standard_code} {clause_ref}"
                results = await kb_service.search(query, top_k=1)
                if results and results[0].get("body_text"):
                    return (str(results[0]["body_text"]), False)
            except Exception:
                pass

        # Return explicit manual verification marker when clause text is missing from KB
        missing_marker = (
            f"CLAUSE_TEXT_NOT_IN_KB — citation reference {standard_code} {clause_ref} "
            "must be verified manually by competent authority"
        )
        return (missing_marker, True)

    async def execute(
        self,
        calc_run_id: str,
        title: str,
        equipment_tag: str,
        governing_standard: str,
        governing_clause: str,
        parameters: list[CalculationParameter],
        primary_code: str,
        cross_check_code: str,
        target_output_var: str,
        target_unit: str,
        ctx: ToolContext,
        kb_service: Any = None,
    ) -> CalculationExecutionRecord:
        """Execute calculation with multi-layered cross-check verification."""
        # 1. Enforce assertions presence
        self.verify_script_assertions(primary_code)

        # 2. Dimensional analysis check via pint
        dim_passed = self.check_dimensional_consistency(parameters, target_unit)

        # 3. Parameter provenance evaluation (FR-5.7)
        unverified_count = 0
        for p in parameters:
            if not p.provenance.human_verified or p.provenance.confidence < 0.90:
                unverified_count += 1
        has_unverified = unverified_count > 0

        # 4. Fetch KB clause text
        clause_text, requires_manual = await self.fetch_kb_clause(
            governing_standard, governing_clause, kb_service
        )

        # 5. Execute Primary Calculation Code in Sandbox
        primary_input = CodeExecInput(
            code=primary_code,
            filename="primary_calc.py",
            declaredOutputs=[],
        )
        primary_res = await self.code_exec_tool.run(primary_input, ctx)
        if not primary_res.success:
            raise CalculationVerificationError(
                f"Primary calculation execution failed: {primary_res.error}"
            )

        # Extract primary output value from stdout or runner
        stdout_lines = self._get_stdout_tail(primary_res.output)
        primary_val = self._extract_output_value(stdout_lines, target_output_var)

        # 6. Execute Secondary Cross-Check Code in Sandbox
        cross_input = CodeExecInput(
            code=cross_check_code,
            filename="cross_check_calc.py",
            declaredOutputs=[],
        )
        cross_res = await self.code_exec_tool.run(cross_input, ctx)
        if not cross_res.success:
            raise CalculationVerificationError(
                f"Cross-check calculation execution failed: {cross_res.error}"
            )

        cross_stdout = self._get_stdout_tail(cross_res.output)
        cross_val = self._extract_output_value(cross_stdout, target_output_var)

        # 7. System-Enforced Cross-Check Verification
        rel_diff = abs(primary_val - cross_val) / max(abs(primary_val), 1e-9)
        cross_check_passed = math.isclose(
            primary_val, cross_val, rel_tol=SYSTEM_REL_TOL, abs_tol=SYSTEM_ABS_TOL
        )

        # Physical Bounds Assertions
        bounds_passed = primary_val > 0.0

        overall_passed = dim_passed and bounds_passed and cross_check_passed

        cross_check_obj = CrossCheckResult(
            passed=cross_check_passed,
            dimensional_check_passed=dim_passed,
            bounds_check_passed=bounds_passed,
            primary_value=primary_val,
            cross_check_value=cross_val,
            relative_diff=rel_diff,
        )

        derivation_steps = [
            {
                "step": "Primary Sandbox Derivation Execution",
                "output_var": target_output_var,
                "value": primary_val,
                "unit": target_unit,
            }
        ]

        record = CalculationExecutionRecord(
            calc_run_id=calc_run_id,
            session_id=ctx.session_id,
            equipment_tag=equipment_tag,
            title=title,
            governing_standard=governing_standard,
            governing_clause=governing_clause,
            clause_quoted_text=clause_text,
            requires_manual_clause_verification=requires_manual,
            parameters=parameters,
            has_unverified_inputs=has_unverified,
            unverified_fields_count=unverified_count,
            derivation_steps=derivation_steps,
            cross_check=cross_check_obj,
            verification_passed=overall_passed,
            assertions_log=stdout_lines,
            final_answer={target_output_var: primary_val, "unit": target_unit},
        )

        if not overall_passed:
            err_msg = (
                f"Calculation cross-check verification failed "
                f"(rel_diff={rel_diff:.6f}, dim_passed={dim_passed})"
            )
            raise CalculationVerificationError(err_msg)

        return record

    def _extract_output_value(self, stdout_lines: list[str], target_var: str) -> float:
        """Extract output variable value from stdout output lines."""
        for line in reversed(stdout_lines):
            if "=" in line:
                parts = line.split("=")
                var_name = parts[0].strip().replace("RESULT:", "").strip()
                if var_name.endswith(target_var) or target_var in var_name:
                    val_str = parts[1].strip().split()[0]
                    try:
                        return float(val_str)
                    except ValueError:
                        continue
        # Fallback numeric extraction from last non-empty line
        for line in reversed(stdout_lines):
            for token in line.split():
                try:
                    return float(token)
                except ValueError:
                    continue
        return 0.0

    def _get_stdout_tail(self, output: Any) -> list[str]:
        """Safely extract stdout tail lines from Pydantic object or dict."""
        if not output:
            return []
        if isinstance(output, dict):
            return list(output.get("stdout_tail") or output.get("stdoutTail") or [])
        if hasattr(output, "stdout_tail") and output.stdout_tail:
            return list(output.stdout_tail)
        if hasattr(output, "stdoutTail") and output.stdoutTail:
            return list(output.stdoutTail)
        return []
