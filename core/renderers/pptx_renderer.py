"""PPTX Renderer — Generates PowerPoint presentation decks from validated JSON schemas.

Creates structured review decks with metric cards, tables, slide citations, and
non-removable system provenance footer slides conforming to PSU engineering standards.
"""

from pathlib import Path
import re
from typing import Any

import pptx
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

from renderers.schemas import ReviewDeckSchema, SystemProvenanceMetadata
from renderers.templates import TemplateManager


def _is_numeric_val(val: str) -> bool:
    """Check if string is numeric for column right-alignment."""
    clean = re.sub(r"[,%\s]", "", str(val).strip())
    return bool(re.match(r"^-?\d+(\.\d+)?$", clean))


class PptxRenderer:
    """Renderer for PowerPoint (.pptx) presentation decks conforming to SWARAJ design tokens."""

    def __init__(self, template_manager: TemplateManager | None = None) -> None:
        self.template_manager = template_manager or TemplateManager()

    def render_review_deck(
        self,
        data: ReviewDeckSchema,
        prov: SystemProvenanceMetadata,
        output_path: Path,
        template_name: str | None = "review_deck.pptx",
    ) -> Path:
        """Render ReviewDeckSchema to .pptx presentation file."""
        template_file = (
            self.template_manager.find_template(template_name) if template_name else None
        )

        if template_file and template_file.exists():
            prs = Presentation(str(template_file))
        else:
            prs = Presentation()

        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

        blank_layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[0]

        # 1. Title Slide (Optical Center)
        title_slide = prs.slides.add_slide(blank_layout)
        t_box = title_slide.shapes.add_textbox(Inches(1.0), Inches(2.4), Inches(11.333), Inches(2.6))
        tf = t_box.text_frame
        tf.word_wrap = True

        p_main = tf.paragraphs[0]
        p_main.text = data.title
        p_main.font.name = "Calibri"
        p_main.font.size = Pt(36)
        p_main.font.bold = True
        p_main.font.color.rgb = RGBColor(0x1F, 0x23, 0x28)

        if data.subtitle:
            p_sub = tf.add_paragraph()
            p_sub.text = data.subtitle
            p_sub.font.name = "Calibri"
            p_sub.font.size = Pt(16)
            p_sub.font.color.rgb = RGBColor(0x57, 0x60, 0x6A)
            p_sub.space_before = Pt(10)

        self._add_slide_footer(title_slide, prov)

        # 2. Content Slides
        for slide_data in data.slides:
            slide = prs.slides.add_slide(blank_layout)
            self._build_slide_header(slide, slide_data.title)

            # Bullets (Max 6)
            if slide_data.bullets:
                tb = slide.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(11.7), Inches(3.6))
                tf_b = tb.text_frame
                tf_b.word_wrap = True
                for idx, bullet in enumerate(slide_data.bullets[:6]):
                    p = tf_b.add_paragraph() if idx > 0 else tf_b.paragraphs[0]
                    p.text = f"• {bullet}"
                    p.font.name = "Calibri"
                    p.font.size = Pt(14)
                    p.font.color.rgb = RGBColor(0x1F, 0x23, 0x28)
                    p.space_after = Pt(8)

            # Key Metrics Cards (Max 4, Value dominates, Label recedes)
            if slide_data.key_metrics:
                cards = slide_data.key_metrics[:4]
                card_width = Inches(2.7)
                card_gap = Inches(0.3)
                start_left = Inches(0.8)

                for idx, metric in enumerate(cards):
                    c_left = start_left + idx * (card_width + card_gap)
                    shape = slide.shapes.add_shape(1, c_left, Inches(4.8), card_width, Inches(1.4))
                    shape.fill.solid()
                    shape.fill.fore_color.rgb = RGBColor(0xF6, 0xF8, 0xFA)
                    shape.line.color.rgb = RGBColor(0xD0, 0xD7, 0xDE)
                    shape.line.width = Pt(0.75)

                    mtf = shape.text_frame
                    mtf.word_wrap = True
                    mtf.margin_left = Inches(0.15)
                    mtf.margin_right = Inches(0.15)
                    mtf.margin_top = Inches(0.12)
                    mtf.margin_bottom = Inches(0.12)

                    for k, v in metric.items():
                        # Label: 10pt uppercase dim
                        p_lbl = mtf.paragraphs[0]
                        p_lbl.text = str(k).upper()
                        p_lbl.font.name = "Calibri"
                        p_lbl.font.size = Pt(9.5)
                        p_lbl.font.bold = True
                        p_lbl.font.color.rgb = RGBColor(0x57, 0x60, 0x6A)

                        # Value: 26pt mono bold --text
                        p_val = mtf.add_paragraph()
                        p_val.text = str(v)
                        p_val.font.name = "IBM Plex Mono"
                        p_val.font.size = Pt(24)
                        p_val.font.bold = True
                        p_val.font.color.rgb = RGBColor(0x1F, 0x23, 0x28)
                        p_val.space_before = Pt(4)

            # Tables (Max 9 rows)
            if slide_data.table_headers and slide_data.table_rows:
                rows_data = slide_data.table_rows[:9]
                rows_count = len(rows_data) + 1
                cols_count = len(slide_data.table_headers)
                t_shape = slide.shapes.add_table(
                    rows_count, cols_count, Inches(0.8), Inches(1.5), Inches(11.7), Inches(3.2)
                )
                tbl = t_shape.table

                # Detect numeric columns
                num_cols = set()
                for c_idx in range(cols_count):
                    col_vals = [r[c_idx] for r in rows_data if c_idx < len(r)]
                    if col_vals and all(_is_numeric_val(v) for v in col_vals if v):
                        num_cols.add(c_idx)

                # Headers
                for col_idx, hdr in enumerate(slide_data.table_headers):
                    cell = tbl.cell(0, col_idx)
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = RGBColor(0x1F, 0x23, 0x28)
                    p = cell.text_frame.paragraphs[0]
                    p.text = hdr
                    p.font.name = "Calibri"
                    p.font.size = Pt(10)
                    p.font.bold = True
                    p.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                    p.alignment = PP_ALIGN.RIGHT if col_idx in num_cols else PP_ALIGN.LEFT

                # Rows
                for row_idx, row in enumerate(rows_data):
                    for col_idx, val in enumerate(row):
                        if col_idx < cols_count:
                            cell = tbl.cell(row_idx + 1, col_idx)
                            p = cell.text_frame.paragraphs[0]
                            p.text = val
                            p.font.name = "IBM Plex Mono" if col_idx in num_cols else "Calibri"
                            p.font.size = Pt(10)
                            p.font.color.rgb = RGBColor(0x1F, 0x23, 0x28)
                            p.alignment = PP_ALIGN.RIGHT if col_idx in num_cols else PP_ALIGN.LEFT

            # Citations block
            if slide_data.citations:
                cit_tb = slide.shapes.add_textbox(Inches(0.8), Inches(6.35), Inches(11.7), Inches(0.35))
                cit_p = cit_tb.text_frame.paragraphs[0]
                c_text = "Sources: " + ", ".join(f"[{c.doc_id} §{c.clause_or_section}]" for c in slide_data.citations)
                cit_p.text = c_text
                cit_p.font.name = "IBM Plex Mono"
                cit_p.font.size = Pt(9)
                cit_p.font.color.rgb = RGBColor(0x57, 0x60, 0x6A)

            self._add_slide_footer(slide, prov)

        # 3. Provenance Attestation Slide
        prov_slide = prs.slides.add_slide(blank_layout)
        self._build_slide_header(prov_slide, "SYSTEM PROVENANCE & AUDIT ATTESTATION")

        p_tb = prov_slide.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(11.7), Inches(4.8))
        p_tf = p_tb.text_frame
        p_tf.word_wrap = True

        p_warn = p_tf.paragraphs[0]
        p_warn.text = "DRAFT — REQUIRES APPROVAL BY COMPETENT AUTHORITY"
        p_warn.font.name = "IBM Plex Mono"
        p_warn.font.size = Pt(14)
        p_warn.font.bold = True
        p_warn.font.color.rgb = RGBColor(0xF5, 0x9E, 0x0B)  # --verify

        records = [
            f"Execution Run ID: {prov.run_id}",
            f"Models Utilized: {', '.join(prov.models_used)}",
            f"Minimum Confidence Score: {prov.min_confidence:.2f}",
            f"Human-Verified Field Count: {prov.human_verified_count}",
            f"Sources Cited ({len(prov.sources_cited)}): {', '.join(prov.sources_cited)}",
            f"Generation Timestamp: {prov.timestamp_utc}",
        ]
        for rec in records:
            p = p_tf.add_paragraph()
            p.text = f"• {rec}"
            p.font.name = "IBM Plex Mono"
            p.font.size = Pt(11)
            p.font.color.rgb = RGBColor(0x1F, 0x23, 0x28)
            p.space_before = Pt(6)

        self._add_slide_footer(prov_slide, prov)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        prs.save(str(output_path))
        return output_path

    def _build_slide_header(self, slide: pptx.slide.Slide, title_text: str) -> None:
        """Build standard slide header with strict vertical rhythm."""
        tb = slide.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(11.7), Inches(0.65))
        p = tb.text_frame.paragraphs[0]
        p.text = title_text
        p.font.name = "Calibri"
        p.font.size = Pt(22)
        p.font.bold = True
        p.font.color.rgb = RGBColor(0x1F, 0x23, 0x28)

        # Hairline rule locked at Y=1.25"
        line = slide.shapes.add_shape(1, Inches(0.8), Inches(1.25), Inches(11.7), Inches(0.01))
        line.fill.solid()
        line.fill.fore_color.rgb = RGBColor(0xD0, 0xD7, 0xDE)
        line.line.color.rgb = RGBColor(0xD0, 0xD7, 0xDE)

    def _add_slide_footer(self, slide: pptx.slide.Slide, prov: SystemProvenanceMetadata) -> None:
        """Add restrained 9pt footer locked at bottom margin."""
        tb = slide.shapes.add_textbox(Inches(0.8), Inches(6.9), Inches(11.7), Inches(0.35))
        p = tb.text_frame.paragraphs[0]
        sources_cnt = len(prov.sources_cited) if prov.sources_cited else 0
        p.text = f"SWARAJ AIR-GAPPED WORKBENCH  |  CONFIDENTIAL  |  Run ID: {prov.run_id}  |  Sources: {sources_cnt}"
        p.font.name = "IBM Plex Mono"
        p.font.size = Pt(8.5)
        p.font.color.rgb = RGBColor(0x57, 0x60, 0x6A)
