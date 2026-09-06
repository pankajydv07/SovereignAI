"""Derivation Formatter — Formats CalculationExecutionRecord into structured sections."""

from typing import Any

from calc.models import CalculationExecutionRecord


class DerivationFormatter:
    """Formats calculation execution records into deliverable derivation blocks."""

    @staticmethod
    def format_docx_derivation(record: CalculationExecutionRecord) -> dict[str, Any]:
        """Build structured dictionary for DOCX calculation derivation section."""
        given_rows = []
        for p in record.parameters:
            v_status = (
                "VERIFIED"
                if p.provenance.human_verified
                else f"UNVERIFIED ({p.provenance.confidence:.0%})"
            )
            given_rows.append(
                {
                    "symbol": p.symbol,
                    "name": p.name,
                    "value": f"{p.value} {p.unit}",
                    "source": p.provenance.source_doc_id,
                    "status": v_status,
                }
            )

        steps = []
        for d in record.derivation_steps:
            step_name = d.get("step", "Step")
            var_name = d.get("output_var", "out")
            val = d.get("value")
            unit = d.get("unit", "")
            steps.append(f"{step_name}: {var_name} = {val} {unit}".strip())

        return {
            "title": record.title,
            "equipment_tag": record.equipment_tag,
            "governing_code": f"{record.governing_standard} {record.governing_clause}",
            "clause_quoted_text": record.clause_quoted_text,
            "requires_manual": record.requires_manual_clause_verification,
            "given_values": given_rows,
            "derivation_steps": steps,
            "cross_check_status": "PASSED" if record.cross_check.passed else "FAILED",
            "cross_check_diff": f"{record.cross_check.relative_diff:.6f}",
            "final_answer": record.final_answer,
            "has_unverified_inputs": record.has_unverified_inputs,
        }
