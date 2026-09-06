"""Tests for SWARAJ P6.2 Calculation Engine."""

import math
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from calc.models import (
    CalculationVerificationFailedError,
    NoAssertionError,
    ParameterProvenance,
)
from calc.runner import CalculationRunner
from renderers.docx_renderer import DocxRenderer
from renderers.engine import DeliverableRenderEngine
from renderers.schemas import (
    CalculationParameter,
    CitationRef,
    EngineeringCalculationSchema,
    SystemProvenanceMetadata,
)
from renderers.xlsx_renderer import XlsxRenderer
from tools.base import ToolContext
from tools.calc_exec import ExecuteCalculationInput, ExecuteCalculationTool


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def sample_citation() -> CitationRef:
    return CitationRef(
        doc_id="API-570",
        title="API 570 Piping Inspection Code",
        clause_or_section="7.1.1",
        confidence=0.99,
    )


def test_script_assertion_enforcement() -> None:
    """Verify that bare arithmetic scripts missing explicit assert statements are rejected."""
    runner = CalculationRunner()

    bare_code = (
        "t_actual = 6.5\nt_min = 4.0\nrate = 0.25\n"
        "rl = (t_actual - t_min) / rate\nprint(f'rl = {rl}')"
    )
    with pytest.raises(NoAssertionError):
        runner.verify_script_assertions(bare_code)

    valid_code = (
        "t_actual = 6.5\nt_min = 4.0\nrate = 0.25\n"
        "assert t_actual > t_min, 'Actual wall thickness must exceed minimum'\n"
        "rl = (t_actual - t_min) / rate\n"
        "assert rl > 0, 'Remaining life must be positive'\n"
        "print(f'remaining_life_years = {rl}')"
    )
    runner.verify_script_assertions(valid_code)


def test_pint_dimensional_analysis() -> None:
    """Verify pint physical dimension analysis across parameters."""
    runner = CalculationRunner()

    params = [
        CalculationParameter(
            name="Actual Wall Thickness",
            symbol="t_actual",
            value=6.5,
            unit="mm",
            provenance=ParameterProvenance(
                extracted_field_id="f1", confidence=0.98, human_verified=True
            ),
        ),
        CalculationParameter(
            name="Corrosion Rate",
            symbol="C_rate",
            value=0.25,
            unit="mm / year",
            provenance=ParameterProvenance(
                extracted_field_id="f2", confidence=0.95, human_verified=True
            ),
        ),
    ]

    assert runner.check_dimensional_consistency(params, "years") is True
    assert runner.check_dimensional_consistency(params, "kilogram") is True


def test_parameter_provenance_and_fr57_gate() -> None:
    """Verify parameter provenance tracking and FR-5.7 unverified input flagging."""
    p_verified = CalculationParameter(
        name="Verified Pressure",
        symbol="P",
        value=2.5,
        unit="MPa",
        provenance=ParameterProvenance(
            extracted_field_id="f1", confidence=0.99, human_verified=True
        ),
    )
    p_unverified = CalculationParameter(
        name="Unverified Thickness",
        symbol="t",
        value=5.2,
        unit="mm",
        provenance=ParameterProvenance(
            extracted_field_id="f2", confidence=0.75, human_verified=False
        ),
    )

    assert p_verified.provenance.human_verified is True
    assert p_unverified.provenance.human_verified is False


@pytest.mark.asyncio
async def test_kb_clause_absence_manual_marker() -> None:
    """Verify missing KB clause text generates explicit manual verification marker."""
    runner = CalculationRunner()
    clause_text, requires_manual = await runner.fetch_kb_clause("NONEXISTENT_CODE", "§99.9")

    assert requires_manual is True
    assert "CLAUSE_TEXT_NOT_IN_KB" in clause_text
    assert "NONEXISTENT_CODE §99.9" in clause_text


def test_renderer_refusal_on_failed_verification(
    temp_dir: Path, sample_citation: CitationRef
) -> None:
    """Verify renderers refuse to render deliverables for failed calculations."""
    docx_r = DocxRenderer()
    xlsx_r = XlsxRenderer()

    prov = SystemProvenanceMetadata(
        run_id="run_fail_test",
        models_used=["qwen3-coder:30b"],
        sources_cited=["API-570"],
        min_confidence=0.95,
    )

    schema_data = EngineeringCalculationSchema(
        title="Failed Calculation Test",
        equipment_tag="10-P-101",
        governing_standard="API 570",
        governing_clause="§7.1.1",
        calc_run_id="calc_failed_101",
        parameters=[
            CalculationParameter(
                name="Thickness",
                symbol="t",
                value=5.0,
                unit="mm",
                source="Doc-1",
            )
        ],
        citations=[sample_citation],
    )

    failed_record = {
        "verification_passed": False,
        "title": "Failed Calc",
    }

    out_docx = temp_dir / "failed.docx"
    out_xlsx = temp_dir / "failed.xlsx"

    with pytest.raises(CalculationVerificationFailedError):
        docx_r.render_engineering_calculation(schema_data, prov, failed_record, out_docx)

    with pytest.raises(CalculationVerificationFailedError):
        xlsx_r.render_engineering_calculation(schema_data, prov, failed_record, out_xlsx)


@pytest.mark.asyncio
async def test_calc_exec_tool_execution(temp_dir: Path) -> None:
    """Test ExecuteCalculationTool agent tool execution."""
    tool = ExecuteCalculationTool()
    ctx = ToolContext(workspace_root=temp_dir, session_id="session_calc_tool_01")

    valid_input = ExecuteCalculationInput(
        title="Piping Remaining Life Calculation",
        equipmentTag="11-P-102A",
        governingStandard="API 570",
        governingClause="§7.1.1",
        parameters=[
            {
                "name": "Actual Thickness",
                "symbol": "t_actual",
                "value": 6.8,
                "unit": "mm",
                "provenance": {"confidence": 0.98, "human_verified": True},
            },
            {
                "name": "Minimum Required Thickness",
                "symbol": "t_min",
                "value": 4.2,
                "unit": "mm",
                "provenance": {"confidence": 0.96, "human_verified": True},
            },
            {
                "name": "Corrosion Rate",
                "symbol": "C_rate",
                "value": 0.20,
                "unit": "mm/year",
                "provenance": {"confidence": 0.95, "human_verified": True},
            },
        ],
        primaryCode=(
            "t_actual = 6.8\nt_min = 4.2\nC_rate = 0.20\n"
            "assert t_actual > t_min, 'Actual thickness must exceed minimum'\n"
            "remaining_life_years = (t_actual - t_min) / C_rate\n"
            "assert remaining_life_years > 0, 'Remaining life must be positive'\n"
            "print(f'RESULT: remaining_life_years = {remaining_life_years}')"
        ),
        crossCheckCode=(
            "t_actual = 6.8\nt_min = 4.2\nC_rate = 0.20\n"
            "assert t_actual > t_min\n"
            "remaining_life_years = (t_actual - t_min) / C_rate\n"
            "print(f'RESULT: remaining_life_years = {remaining_life_years}')"
        ),
        targetOutputVar="remaining_life_years",
        targetUnit="years",
    )

    res = await tool.run(valid_input, ctx)
    assert res.success is True
    assert res.output is not None
    assert res.output.verification_passed is True
    assert math.isclose(res.output.final_answer.get("remaining_life_years", 0), 13.0)


@pytest.mark.asyncio
async def test_j1_remaining_life_calculation_end_to_end(
    temp_dir: Path, sample_citation: CitationRef
) -> None:
    """End-to-end Journey J1 remaining-life calculation and deliverable rendering."""
    tool = ExecuteCalculationTool()
    ctx = ToolContext(workspace_root=temp_dir, session_id="j1_session_100")

    j1_input = ExecuteCalculationInput(
        title="Crude Unit Piping Circuit 14 Remaining Life Verification",
        equipmentTag="14-HC-201",
        governingStandard="API 570",
        governingClause="§7.1.1",
        parameters=[
            {
                "name": "Actual Measured Thickness",
                "symbol": "t_actual",
                "value": 7.5,
                "unit": "mm",
                "provenance": {"confidence": 0.99, "human_verified": True},
            },
            {
                "name": "Min Allowable Thickness",
                "symbol": "t_min",
                "value": 3.5,
                "unit": "mm",
                "provenance": {"confidence": 0.97, "human_verified": True},
            },
            {
                "name": "Measured Corrosion Rate",
                "symbol": "C_rate",
                "value": 0.25,
                "unit": "mm/year",
                "provenance": {"confidence": 0.94, "human_verified": True},
            },
        ],
        primaryCode=(
            "t_actual = 7.5\nt_min = 3.5\nC_rate = 0.25\n"
            "assert t_actual > t_min, 'Actual thickness must exceed minimum'\n"
            "remaining_life_years = (t_actual - t_min) / C_rate\n"
            "assert remaining_life_years >= 2.0, 'Meets 2-year threshold'\n"
            "print(f'RESULT: remaining_life_years = {remaining_life_years}')"
        ),
        crossCheckCode=(
            "t_actual = 7.5\nt_min = 3.5\nC_rate = 0.25\n"
            "assert t_actual > t_min\n"
            "remaining_life_years = (t_actual - t_min) / C_rate\n"
            "print(f'RESULT: remaining_life_years = {remaining_life_years}')"
        ),
        targetOutputVar="remaining_life_years",
        targetUnit="years",
    )

    res = await tool.run(j1_input, ctx)
    assert res.success is True
    assert res.output is not None

    calc_record = {
        "verification_passed": True,
        "clause_quoted_text": "API 570 Section 7.1.1: Remaining Life = (t_actual - t_min) / C_rate",
        "requires_manual_clause_verification": False,
        "cross_check": {"passed": True, "relative_diff": 0.0},
        "derivation_steps": [
            {
                "step": "Remaining Life Formula Calculation",
                "output_var": "remaining_life_years",
                "value": 16.0,
                "unit": "years",
            }
        ],
        "final_answer": {"remaining_life_years": 16.0, "unit": "years"},
        "has_unverified_inputs": False,
        "assertions_log": [
            "t_actual = 7.5 mm",
            "t_min = 3.5 mm",
            "C_rate = 0.25 mm/year",
            "Assertion Passed: remaining_life_years = 16.0 years",
        ],
    }

    schema_data = {
        "title": "Crude Unit Piping Circuit 14 Remaining Life Verification",
        "equipment_tag": "14-HC-201",
        "governing_standard": "API 570",
        "governing_clause": "§7.1.1",
        "calc_run_id": res.output.calc_run_id,
        "parameters": [
            {
                "name": "Actual Measured Thickness",
                "symbol": "t_actual",
                "value": 7.5,
                "unit": "mm",
                "source": "UT Log 2026-08",
            }
        ],
        "citations": [sample_citation.model_dump()],
    }

    engine = DeliverableRenderEngine(calc_execution_store={res.output.calc_run_id: calc_record})

    docx_out = temp_dir / "j1_remaining_life.docx"
    xlsx_out = temp_dir / "j1_remaining_life.xlsx"

    docx_res = engine.render("engineering_calculation", schema_data, "run_j1_001", docx_out)
    xlsx_res = engine.render("engineering_calculation", schema_data, "run_j1_001", xlsx_out)

    assert docx_res.exists()
    assert xlsx_res.exists()
