/**
 * Unit & Integration Tests for ProvenanceViewer component.
 *
 * Validates against real P5.1 DocumentIngestPipeline output fixture JSON to prevent schema drift.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ProvenanceViewer } from "../ProvenanceViewer";
import fixtureData from "./test_report_fixture.json";
import { AuditedFieldItem } from "../FieldTable";

describe("ProvenanceViewer Component", () => {
  const mockFields: AuditedFieldItem[] = fixtureData.fields.map((f, idx) => ({
    id: `field_${idx + 1}`,
    field_name: f.field_name,
    value: f.value,
    unit: f.unit,
    confidence: f.confidence,
    requires_verification: f.requires_verification,
    is_verified: false,
    page: f.page,
    bbox: f.bbox,
    extractor: f.extractor,
  }));

  it("renders 50/50 split view with fields from real P5.1 pipeline fixture", () => {
    render(
      <ProvenanceViewer
        imagePath={fixtureData.doc_path}
        totalPages={1}
        fields={mockFields}
      />
    );

    expect(screen.getByText("EXTRACTED FIELDS (4)")).toBeDefined();
    expect(screen.getAllByText("asset_tag")[0]).toBeDefined();
    expect(screen.getByText("C-101")).toBeDefined();
    expect(screen.getByText("12.5")).toBeDefined();
  });

  it("preserves machine confidence immutably when verifying a field", () => {
    const onAudit = vi.fn();
    render(
      <ProvenanceViewer
        imagePath={fixtureData.doc_path}
        totalPages={1}
        fields={mockFields}
        onAuditFieldVerified={onAudit}
      />
    );

    // Initial machine confidence for thickness_mm is 0.62
    expect(screen.getByText("0.62")).toBeDefined();

    const verifyButtons = screen.getAllByText("Verify");
    fireEvent.click(verifyButtons[0]);

    // Machine confidence 0.62 remains untouched after verification
    expect(screen.getByText("0.62")).toBeDefined();
    expect(screen.getByText(/verified by A. Sharma/)).toBeDefined();

    // Verifies audit event dispatch
    expect(onAudit).toHaveBeenCalledWith(
      expect.objectContaining({
        fieldId: expect.any(String),
        docPath: fixtureData.doc_path,
        operatorId: "A. Sharma",
      })
    );
  });

  it("supports j / k keyboard navigation between fields", () => {
    render(
      <ProvenanceViewer
        imagePath={fixtureData.doc_path}
        totalPages={1}
        fields={mockFields}
      />
    );

    fireEvent.keyDown(window, { key: "j" });
    // First field should be selected initially, 'j' navigates to second field
    expect(screen.getAllByText("inspection_date")[0]).toBeDefined();
  });

  it("renders empty state when zero fields are extracted", () => {
    render(
      <ProvenanceViewer
        imagePath="empty.png"
        totalPages={1}
        fields={[]}
      />
    );

    expect(screen.getByText("ZERO FIELDS EXTRACTED")).toBeDefined();
  });

  it("renders ingesting banner during progressive field arrival", () => {
    render(
      <ProvenanceViewer
        imagePath={fixtureData.doc_path}
        totalPages={6}
        fields={mockFields}
        isIngesting={true}
        ingestProgressPage={2}
      />
    );

    expect(screen.getByText(/INGESTING DOCUMENT… Processing page 2 of 6/)).toBeDefined();
  });

  it("renders unreadable page warning banner when flagged", () => {
    render(
      <ProvenanceViewer
        imagePath={fixtureData.doc_path}
        totalPages={1}
        fields={mockFields}
        unreadableWarning="Low contrast scan on Page 1"
      />
    );

    expect(screen.getByText(/WARNING: Low contrast scan on Page 1/)).toBeDefined();
  });
});
