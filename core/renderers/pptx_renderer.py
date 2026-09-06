"""PPTX Renderer — Generates PowerPoint presentation decks from validated JSON schemas.

Creates structured review decks with metric cards, tables, slide citations, and
non-removable system provenance footer slides.
"""

from pathlib import Path
from typing import Any

import pptx
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from renderers.schemas import ReviewDeckSchema, SystemProvenanceMetadata
from renderers.templates import TemplateManager


class PptxRenderer:
    """Renderer for PowerPoint (.pptx) presentation decks."""

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

        prs.slide_width = Inches(13.33)
        prs.slide_height = Inches(7.5)

        # Title Slide
        title_slide = prs.slides.add_slide(prs.slide_layouts[0])
        title_box = title_slide.shapes.title
        title_box.text = data.title
        if data.subtitle and title_slide.placeholders[1]:
            title_slide.placeholders[1].text = data.subtitle
        self._add_slide_footer(title_slide, prov)

        # Content Slides
        blank_layout = prs.slide_layouts[6]
        for slide_data in data.slides:
            slide = prs.slides.add_slide(blank_layout)
            self._build_slide_header(slide, slide_data.title)

            # Bullets
            if slide_data.bullets:
                tb = slide.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(11.7), Inches(3.5))
                tf = tb.text_frame
                tf.word_wrap = True
                for bullet in slide_data.bullets:
                    p = tf.add_paragraph()
                    p.text = f"• {bullet}"
                    p.font.size = Pt(18)

            # Key Metrics Cards
            if slide_data.key_metrics:
                left_start: Any = Inches(0.8)
                for metric in slide_data.key_metrics:
                    mb = slide.shapes.add_textbox(left_start, Inches(5.2), Inches(3.5), Inches(1.2))
                    mtf = mb.text_frame
                    mtf.word_wrap = True
                    for k, v in metric.items():
                        p1 = mtf.add_paragraph()
                        p1.text = str(k).upper()
                        p1.font.size = Pt(11)
                        p1.font.bold = True
                        p2 = mtf.add_paragraph()
                        p2.text = str(v)
                        p2.font.size = Pt(20)
                        p2.font.bold = True
                        p2.font.color.rgb = RGBColor(0x10, 0xB9, 0x81)  # type: ignore[no-untyped-call]
                    left_start = left_start + Inches(3.8)

            # Table
            if slide_data.table_headers and slide_data.table_rows:
                rows_count = len(slide_data.table_rows) + 1
                cols_count = len(slide_data.table_headers)
                table_shape = slide.shapes.add_table(
                    rows_count, cols_count, Inches(0.8), Inches(2.0), Inches(11.7), Inches(3.0)
                )
                tbl = table_shape.table
                for col_idx, hdr in enumerate(slide_data.table_headers):
                    tbl.cell(0, col_idx).text = hdr
                for row_idx, row in enumerate(slide_data.table_rows):
                    for col_idx, val in enumerate(row):
                        tbl.cell(row_idx + 1, col_idx).text = val

            # Citations block
            if slide_data.citations:
                cit_tb = slide.shapes.add_textbox(
                    Inches(0.8), Inches(6.3), Inches(11.7), Inches(0.4)
                )
                cit_p = cit_tb.text_frame.paragraphs[0]
                c_text = "Sources: " + ", ".join(
                    f"[{c.doc_id} §{c.clause_or_section}]" for c in slide_data.citations
                )
                cit_p.text = c_text
                cit_p.font.size = Pt(10)
                cit_p.font.color.rgb = RGBColor(0x4C, 0x8D, 0xF6)  # type: ignore[no-untyped-call]

            self._add_slide_footer(slide, prov)

        # Final Provenance Slide
        prov_slide = prs.slides.add_slide(blank_layout)
        self._build_slide_header(prov_slide, "SYSTEM PROVENANCE & AUDIT ATTESTATION")
        p_tb = prov_slide.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(11.7), Inches(4.5))
        p_tf = p_tb.text_frame
        p_tf.word_wrap = True

        p1 = p_tf.add_paragraph()
        p1.text = f"*** {prov.draft_warning} ***"
        p1.font.size = Pt(22)
        p1.font.bold = True
        p1.font.color.rgb = RGBColor(0xEF, 0x44, 0x44)  # type: ignore[no-untyped-call]

        lines = [
            f"Execution Run ID: {prov.run_id}",
            f"Models Utilized: {', '.join(prov.models_used)}",
            f"Minimum Confidence Score: {prov.min_confidence:.2f}",
            f"Human-Verified Field Count: {prov.human_verified_count}",
            f"Sources Cited ({len(prov.sources_cited)}): {', '.join(prov.sources_cited)}",
        ]
        for line in lines:
            p = p_tf.add_paragraph()
            p.text = line
            p.font.size = Pt(16)

        self._add_slide_footer(prov_slide, prov)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        prs.save(str(output_path))
        return output_path

    def _build_slide_header(self, slide: pptx.slide.Slide, title_text: str) -> None:
        tb = slide.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(11.7), Inches(0.8))
        p = tb.text_frame.paragraphs[0]
        p.text = title_text
        p.font.size = Pt(24)
        p.font.bold = True
        p.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)  # type: ignore[no-untyped-call]

    def _add_slide_footer(self, slide: pptx.slide.Slide, prov: SystemProvenanceMetadata) -> None:
        tb = slide.shapes.add_textbox(Inches(0.8), Inches(6.9), Inches(11.7), Inches(0.4))
        p = tb.text_frame.paragraphs[0]
        p.text = f"SWARAJ AIR-GAPPED WORKBENCH  |  {prov.draft_warning}  |  Run ID: {prov.run_id}"
        p.font.size = Pt(9)
        p.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)  # type: ignore[no-untyped-call]
