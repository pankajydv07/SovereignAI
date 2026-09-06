"""Execute Calculation Tool — Agent tool for running sandboxed calculations with cross-checks."""

from typing import Any

from pydantic import Field, ValidationError

from calc.models import (
    CalculationParameter,
    CalculationVerificationError,
    NoAssertionError,
)
from calc.runner import CalculationRunner
from protocol.models import ProtocolBaseModel
from tools.base import BaseTool, SideEffect, ToolContext, ToolKind, ToolResult


class ExecuteCalculationInput(ProtocolBaseModel):
    """Input model for calculation execution tool."""

    title: str = Field(description="Calculation title (e.g., Remaining Life Calculation)")
    equipment_tag: str = Field(alias="equipmentTag", description="Equipment tag number")
    governing_standard: str = Field(alias="governingStandard", description="Governing code name")
    governing_clause: str = Field(alias="governingClause", description="Governing clause reference")
    parameters: list[dict[str, Any]] = Field(
        description="Given input parameters with units and provenance"
    )
    primary_code: str = Field(
        alias="primaryCode", description="Primary Python calculation script with assertions"
    )
    cross_check_code: str = Field(
        alias="crossCheckCode", description="Secondary cross-check script for verification"
    )
    target_output_var: str = Field(
        alias="targetOutputVar",
        description="Target output variable name (e.g. remaining_life_years)",
    )
    target_unit: str = Field(alias="targetUnit", description="Target physical unit string")


class ExecuteCalculationOutput(ProtocolBaseModel):
    """Output model for calculation execution tool."""

    calc_run_id: str = Field(alias="calcRunId")
    verification_passed: bool = Field(alias="verificationPassed")
    has_unverified_inputs: bool = Field(alias="hasUnverifiedInputs")
    final_answer: dict[str, Any] = Field(alias="finalAnswer")


class ExecuteCalculationTool(BaseTool[ExecuteCalculationInput, ExecuteCalculationOutput]):
    """Tool for executing sandboxed engineering calculations with unit checks and assertions."""

    name = "calc_exec"
    description = "Execute Python calculation with units, assertions, and cross-check verification"
    kind = ToolKind.EXECUTE
    side_effect = SideEffect.EXEC
    scopes = ["sandbox:exec"]
    timeout_s = 60.0
    is_idempotent = False
    input_model = ExecuteCalculationInput
    output_model = ExecuteCalculationOutput

    def __init__(self, runner: CalculationRunner | None = None) -> None:
        self.runner = runner or CalculationRunner()

    async def run(self, args: ExecuteCalculationInput, ctx: ToolContext) -> ToolResult:
        calc_run_id = f"calc_{ctx.session_id}"

        try:
            param_objs = [CalculationParameter.model_validate(p) for p in args.parameters]

            record = await self.runner.execute(
                calc_run_id=calc_run_id,
                title=args.title,
                equipment_tag=args.equipment_tag,
                governing_standard=args.governing_standard,
                governing_clause=args.governing_clause,
                parameters=param_objs,
                primary_code=args.primary_code,
                cross_check_code=args.cross_check_code,
                target_output_var=args.target_output_var,
                target_unit=args.target_unit,
                ctx=ctx,
            )

            output = ExecuteCalculationOutput(
                calcRunId=record.calc_run_id,
                verificationPassed=record.verification_passed,
                hasUnverifiedInputs=record.has_unverified_inputs,
                finalAnswer=record.final_answer,
            )
            return ToolResult.ok(output)

        except (NoAssertionError, CalculationVerificationError, ValidationError, ValueError) as exc:
            return ToolResult.failed(f"CalculationVerificationError: {exc}")
        except Exception as exc:
            return ToolResult.failed(f"Calculation failed: {exc}")
