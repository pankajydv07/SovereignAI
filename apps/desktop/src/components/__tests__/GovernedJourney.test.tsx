import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ReviewApprovePanel } from "../ReviewApprovePanel";

describe("Governed Deliverable Journey UI Workflow", () => {
  const mockMaker = {
    id: "user_sharma",
    name: "A. Sharma",
    designation: "Senior Inspection Engineer",
  };

  const mockChecker = {
    id: "user_kulkarni",
    name: "P. V. Kulkarni",
    designation: "Chief Manager - Mechanical",
  };

  const mockUnverifiedField = {
    id: "field_cml07_thickness",
    field_name: "t_actual_cml07",
    value: "8.2",
    unit: "mm",
    confidence: null as number | null, // Uncalibrated vision model output
    is_verified: false,
    requires_verification: true,
    page: 1,
    bbox: [0.35, 0.08, 0.42, 0.92] as [number, number, number, number],
    imagePath: "scans/scan_c101_inspection.png",
  };

  const mockCitations = [
    {
      id: "cite-1",
      doc_id: "MRPL-INSP-2026-09",
      title: "MRPL Inspection Report",
      clause_or_section: "p. 1, CML-07",
      claim_text: "Measured wall thickness of 8.2 mm at CML-07 indicates active internal thinning.",
      is_cited: true,
    },
    {
      id: "cite-2",
      doc_id: "API-570",
      title: "API-570 Piping Inspection Code",
      clause_or_section: "Section 7.1.2",
      claim_text: "Sanction 14.8 months extended operational run subject to quarterly UT monitoring.",
      is_cited: true,
    },
  ];

  beforeEach(() => {
    delete (window as any).__TAURI_INTERNALS__;
  });

  afterEach(() => {
    delete (window as any).__TAURI_INTERNALS__;
    vi.restoreAllMocks();
  });

  it("proves complete governed UI lifecycle: vision crop review -> verification -> maker-checker gate -> sealed stamp", async () => {
    const handleApprove = vi.fn();

    // 1. Initial Render: Deliverable contains unverified vision field
    const { rerender } = render(
      <ReviewApprovePanel
        deliverableId="DELIV-C101-2026"
        title="TECHNICAL APPROVAL NOTE: Column C-101 Inspection Sanction"
        subject="Ultrasonic survey & remaining life approval for Crude Distillation Column C-101"
        maker={mockMaker}
        checker={mockChecker}
        currentUser={mockChecker}
        initialFields={[mockUnverifiedField]}
        initialCitations={mockCitations}
        onApproveSuccess={handleApprove}
      />
    );

    // 2. Assert Blocking Banner is active due to unverified vision extraction
    const blockingBanner = screen.getByTestId("blocking-banner");
    expect(blockingBanner).toBeDefined();
    expect(blockingBanner.textContent).toContain("Approval blocked");
    expect(blockingBanner.textContent).toContain("unverified");

    const approveBtn = screen.getByTestId("approve-btn") as HTMLButtonElement;
    expect(approveBtn.disabled).toBe(true);

    // 3. Checker views source crop & verifies provenance
    const jumpLink = screen.getByTestId("jump-unverified-link");
    fireEvent.click(jumpLink);

    const cropPreview = screen.getByTestId("inline-crop-preview");
    expect(cropPreview).toBeDefined();
    expect(screen.getByText(/PAGE 1/)).toBeDefined();

    // Verify the unverified field via InlineCropPreview
    const verifyBtn = screen.getByTestId("confirm-verify-btn");
    fireEvent.click(verifyBtn);

    // 4. Update state with verified field
    const verifiedField = { ...mockUnverifiedField, is_verified: true, requires_verification: false };
    const verifiedCitations = mockCitations.map((c) =>
      c.id === "cite-1" ? { ...c, isVerified: true } : c
    );

    rerender(
      <ReviewApprovePanel
        deliverableId="DELIV-C101-2026"
        title="TECHNICAL APPROVAL NOTE: Column C-101 Inspection Sanction"
        subject="Ultrasonic survey & remaining life approval for Crude Distillation Column C-101"
        maker={mockMaker}
        checker={mockChecker}
        currentUser={mockChecker}
        initialFields={[verifiedField]}
        initialCitations={verifiedCitations}
        onApproveSuccess={handleApprove}
      />
    );

    // 5. Verification unblocks the approval gate
    expect(screen.queryByTestId("blocking-banner")).toBeNull();
    const activeApproveBtn = screen.getByTestId("approve-btn") as HTMLButtonElement;
    expect(activeApproveBtn.disabled).toBe(false);

    // 6. Test Separation of Duties (Maker cannot self-approve)
    rerender(
      <ReviewApprovePanel
        deliverableId="DELIV-C101-2026"
        title="TECHNICAL APPROVAL NOTE: Column C-101 Inspection Sanction"
        subject="Ultrasonic survey & remaining life approval for Crude Distillation Column C-101"
        maker={mockMaker}
        checker={mockChecker}
        currentUser={mockMaker} // Attempted maker self-approval
        initialFields={[verifiedField]}
        initialCitations={verifiedCitations}
        onApproveSuccess={handleApprove}
      />
    );

    const sodBanner = screen.getByTestId("blocking-banner");
    expect(sodBanner.textContent).toContain("You prepared this deliverable");
    expect((screen.getByTestId("approve-btn") as HTMLButtonElement).disabled).toBe(true);

    // 7. Switch back to Checker and complete approval
    rerender(
      <ReviewApprovePanel
        deliverableId="DELIV-C101-2026"
        title="TECHNICAL APPROVAL NOTE: Column C-101 Inspection Sanction"
        subject="Ultrasonic survey & remaining life approval for Crude Distillation Column C-101"
        maker={mockMaker}
        checker={mockChecker}
        currentUser={mockChecker}
        initialFields={[verifiedField]}
        initialCitations={verifiedCitations}
        onApproveSuccess={handleApprove}
      />
    );

    const finalApproveBtn = screen.getByTestId("approve-btn") as HTMLButtonElement;
    fireEvent.click(finalApproveBtn);

    // 8. Assert Approval Stamp is applied
    await waitFor(() => {
      const stamp = screen.getByTestId("approval-stamp-box");
      expect(stamp).toBeDefined();
      expect(stamp.textContent).toContain("APPROVED");
      expect(stamp.textContent).toContain("P. V. Kulkarni");
      expect(stamp.textContent).toContain("A. Sharma");
    });
  });
});
