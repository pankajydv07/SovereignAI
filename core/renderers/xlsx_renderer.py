"""XLSX Renderer — Generates Excel spreadsheets from validated JSON schemas.

Writes live openpyxl Excel formulas (starting with '='), stores evaluated initial
values for self-reading, resolves executed sandbox calculation results via calc_run_id,
and formats a non-removable system provenance audit worksheet.
"""

from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from calc.models import CalculationVerificationFailedError
from renderers.schemas import (
    CostSheetSchema,
    EngineeringCalculationSchema,
    SystemProvenanceMetadata,
)
from renderers.templates import TemplateManager


class XlsxRenderer:
    """Renderer for Excel (.xlsx) spreadsheets."""

    def __init__(self, template_manager: TemplateManager | None = None) -> None:
        self.template_manager = template_manager or TemplateManager()

    def render_cost_sheet(
        self,
        data: CostSheetSchema,
        prov: SystemProvenanceMetadata,
        output_path: Path,
    ) -> Path:
        """Render CostSheetSchema to .xlsx file with live formulas."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Cost Sheet"
        ws.views.sheetView[0].showGridLines = True

        # Header Block
        ws["A1"] = "MANGALORE REFINERY AND PETROCHEMICALS LIMITED"
        ws["A1"].font = Font(name="Calibri", size=14, bold=True, color="1B365D")
        ws["A2"] = f"FINANCIAL IMPLICATION SHEET ({data.currency})"
        ws["A2"].font = Font(name="Calibri", size=12, bold=True)
        prov_status = "YES" if data.provisioned else "NO"
        ws["A3"] = f"Budget Head: {data.budget_head}  |  Provisioned: {prov_status}"
        ws["A3"].font = Font(name="Calibri", size=10, italic=True)

        # Column Headers
        headers = ["Item Description", "Quantity", "Unit Rate", "Amount", "Citations"]
        start_row = 5
        for col_idx, hdr in enumerate(headers, start=1):
            cell = ws.cell(row=start_row, column=col_idx, value=hdr)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Line Items
        curr_row = start_row + 1
        for item in data.items:
            ws.cell(row=curr_row, column=1, value=item.description)
            ws.cell(row=curr_row, column=2, value=item.quantity)
            ws.cell(row=curr_row, column=3, value=item.unit_rate)

            # Live Excel Formula string (e.g. '=B6*C6')
            formula_str = (
                item.formula.format(row=curr_row) if "{row}" in item.formula else item.formula
            )
            if not formula_str.startswith("="):
                formula_str = f"={formula_str}"

            amount_cell = ws.cell(row=curr_row, column=4, value=formula_str)
            amount_cell.number_format = "#,##0.00"

            citations_text = ", ".join(
                f"[{c.doc_id} §{c.clause_or_section}]" for c in item.citations
            )
            ws.cell(row=curr_row, column=5, value=citations_text)
            curr_row += 1

        # Total Row
        ws.cell(row=curr_row, column=1, value="TOTAL FINANCIAL IMPLICATION").font = Font(bold=True)
        total_formula = data.total_formula.format(start=start_row + 1, end=curr_row - 1)
        if not total_formula.startswith("="):
            total_formula = f"={total_formula}"

        tot_cell = ws.cell(row=curr_row, column=4, value=total_formula)
        tot_cell.font = Font(bold=True)
        tot_cell.number_format = "#,##0.00"

        # Auto-adjust column widths
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        # Add Provenance Sheet
        self._add_provenance_sheet(wb, prov)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(str(output_path))
        return output_path

    def render_engineering_calculation(
        self,
        data: EngineeringCalculationSchema,
        prov: SystemProvenanceMetadata,
        calc_execution_record: dict[str, Any] | None,
        output_path: Path,
    ) -> Path:
        """Render EngineeringCalculationSchema using executed sandbox results. Refuses if failed."""
        if not calc_execution_record:
            raise CalculationVerificationFailedError(
                "Refusing to render: calculation execution record absent"
            )

        v_passed = calc_execution_record.get("verification_passed", True)
        if not v_passed:
            raise CalculationVerificationFailedError(
                f"Refusing to render calculation '{data.title}': cross-check verification failed"
            )

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Engineering Calculation"
        ws.views.sheetView[0].showGridLines = True

        ws["A1"] = f"ENGINEERING CALCULATION: {data.title}"
        ws["A1"].font = Font(name="Calibri", size=14, bold=True, color="1B365D")
        ws["A2"] = (
            f"Tag: {data.equipment_tag} | Code: {data.governing_standard} §{data.governing_clause}"
        )
        ws["A2"].font = Font(name="Calibri", size=11, bold=True)
        ws["A3"] = f"Execution Record ID: {data.calc_run_id}"
        ws["A3"].font = Font(name="Calibri", size=10, italic=True)

        # Quoted KB Clause Box
        clause_quoted = calc_execution_record.get("clause_quoted_text", "")
        req_manual = calc_execution_record.get("requires_manual_clause_verification", False)
        ws["A5"] = "GOVERNING CLAUSE (KNOWLEDGE BASE):"
        ws["A5"].font = Font(bold=True)
        ws["A6"] = clause_quoted
        if req_manual:
            ws["A6"].font = Font(bold=True, color="F59E0B")

        # Parameters Table
        ws["A8"] = "1. GIVEN INPUT PARAMETERS"
        ws["A8"].font = Font(bold=True)
        headers = ["Parameter", "Symbol", "Value", "Unit", "Source Tag"]
        for col_idx, hdr in enumerate(headers, start=1):
            c = ws.cell(row=9, column=col_idx, value=hdr)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")

        curr_row = 10
        for param in data.parameters:
            ws.cell(row=curr_row, column=1, value=param.name)
            ws.cell(row=curr_row, column=2, value=param.symbol)
            ws.cell(row=curr_row, column=3, value=param.value)
            ws.cell(row=curr_row, column=4, value=param.unit)
            ws.cell(row=curr_row, column=5, value=param.source)
            curr_row += 1

        # Executed Results Section (From Sandbox Record)
        curr_row += 1
        ws.cell(row=curr_row, column=1, value="2. EXECUTED SANDBOX DERIVATION RESULTS").font = Font(
            bold=True
        )
        curr_row += 1

        computed_outputs = calc_execution_record.get("final_answer", {})
        stdout_tail = calc_execution_record.get("assertions_log", [])

        ws.cell(row=curr_row, column=1, value="Executed Output Variable").font = Font(bold=True)
        ws.cell(row=curr_row, column=2, value="Executed Value").font = Font(bold=True)
        curr_row += 1

        for k, v in computed_outputs.items():
            ws.cell(row=curr_row, column=1, value=k)
            ws.cell(row=curr_row, column=2, value=str(v))
            curr_row += 1

        # Console Trace / Derivation Log
        if stdout_tail:
            curr_row += 1
            ws.cell(row=curr_row, column=1, value="Execution Derivation Log:").font = Font(
                bold=True
            )
            curr_row += 1
            for line in stdout_tail:
                ws.cell(row=curr_row, column=1, value=line)
                curr_row += 1

        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 14)

        self._add_provenance_sheet(wb, prov)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(str(output_path))
        return output_path

    def _add_provenance_sheet(self, wb: openpyxl.Workbook, prov: SystemProvenanceMetadata) -> None:
        """Add non-removable System Provenance Audit sheet."""
        ws = wb.create_sheet(title="Provenance & Audit")
        ws.views.sheetView[0].showGridLines = True

        ws["A1"] = f"*** {prov.draft_warning} ***"
        ws["A1"].font = Font(size=14, bold=True, color="EF4444")

        audit_data = [
            ("Execution Run ID", prov.run_id),
            ("Models Utilized", ", ".join(prov.models_used)),
            ("Minimum Confidence Score", f"{prov.min_confidence:.2f}"),
            ("Human-Verified Fields", prov.human_verified_count),
            ("Sources Cited", ", ".join(prov.sources_cited)),
            ("Attestation Warning", prov.draft_warning),
        ]

        for idx, (label, val) in enumerate(audit_data, start=3):
            c1 = ws.cell(row=idx, column=1, value=label)
            c1.font = Font(bold=True)
            ws.cell(row=idx, column=2, value=str(val))

        ws.column_dimensions["A"].width = 28
        ws.column_dimensions["B"].width = 50
