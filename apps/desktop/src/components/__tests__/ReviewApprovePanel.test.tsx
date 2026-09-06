import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ReviewApprovePanel } from "../ReviewApprovePanel";

describe("ReviewApprovePanel Component", () => {
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

  it("renders deliverable preview on white page in light mode with org letterhead", () => {
    render(
      <ReviewApprovePanel
        deliverableId="DELIV-TEST-101"
        title="TECHNICAL APPROVAL NOTE: Remaining Life Sanction"
        subject="Column C-101 Inspection"
        maker={mockMaker}
        checker={mockChecker}
        currentUser={mockChecker}
      />
    );

    expect(screen.getByTestId("deliverable-paper-page")).toBeDefined();
    expect(screen.getByText("MANGALORE REFINERY AND PETROCHEMICALS LIMITED")).toBeDefined();
    expect(screen.getByText("TECHNICAL APPROVAL NOTE: Remaining Life Sanction")).toBeDefined();
    expect(screen.getByText(/DRAFT — requires approval by competent authority/)).toBeDefined();
  });

  it("enforces separation of duties and blocks approval when maker == currentUser", () => {
    render(
      <ReviewApprovePanel
        deliverableId="DELIV-TEST-101"
        title="TECHNICAL APPROVAL NOTE"
        subject="Column C-101"
        maker={mockMaker}
        checker={mockChecker}
        currentUser={mockMaker} // Same user as maker!
      />
    );

    const banner = screen.getByTestId("blocking-banner");
    expect(banner.textContent).toContain("You prepared this deliverable (A. Sharma)");

    const approveBtn = screen.getByTestId("approve-btn") as HTMLButtonElement;
    expect(approveBtn.disabled).toBe(true);
  });

  it("shows BLOCKING banner and jump link when unverified fields or uncited claims exist", () => {
    render(
      <ReviewApprovePanel
        deliverableId="DELIV-TEST-101"
        title="TECHNICAL APPROVAL NOTE"
        subject="Column C-101"
        maker={mockMaker}
        checker={mockChecker}
        currentUser={mockChecker}
      />
    );

    expect(screen.getByTestId("blocking-banner")).toBeDefined();
    const jumpLink = screen.getByTestId("jump-unverified-link");
    expect(jumpLink).toBeDefined();

    fireEvent.click(jumpLink);
    expect(screen.getByTestId("inline-crop-preview")).toBeDefined();
  });

  it("supports provenance-backed field verification with crop preview to unblock approval", () => {
    const unverifiedFields = [
      {
        id: "f1",
        field_name: "design_pressure",
        value: "2.4",
        unit: "MPa",
        confidence: 0.72,
        is_verified: false,
        requires_verification: true,
        page: 1,
        bbox: [210, 340, 250, 480] as [number, number, number, number],
        imagePath: "scan.pdf",
      },
    ];

    const citations = [
      {
        id: "c1",
        doc_id: "KB-API-570",
        title: "Piping Code",
        clause_or_section: "7.1.2",
        claim_text: "Formula adheres to standard",
        is_cited: true,
      },
    ];

    render(
      <ReviewApprovePanel
        deliverableId="DELIV-TEST-101"
        title="TECHNICAL APPROVAL NOTE"
        subject="Column C-101"
        maker={mockMaker}
        checker={mockChecker}
        currentUser={mockChecker}
        initialFields={unverifiedFields}
        initialCitations={citations}
      />
    );

    // Verify button initially present
    const verifyBtn = screen.getByTestId("verify-field-btn-f1");
    fireEvent.click(verifyBtn);

    // Bounding box crop preview appears
    expect(screen.getByTestId("inline-crop-preview")).toBeDefined();

    // Click confirm verify
    const confirmBtn = screen.getByTestId("confirm-verify-btn");
    fireEvent.click(confirmBtn);

    // Field becomes VERIFIED and approve button becomes enabled!
    expect(screen.getByText("VERIFIED")).toBeDefined();
    const approveBtn = screen.getByTestId("approve-btn") as HTMLButtonElement;
    expect(approveBtn.disabled).toBe(false);
  });

  it("handles Edit & Approve word diff narrative editing", () => {
    render(
      <ReviewApprovePanel
        deliverableId="DELIV-TEST-101"
        title="TECHNICAL APPROVAL NOTE"
        subject="Column C-101"
        maker={mockMaker}
        checker={mockChecker}
        currentUser={mockChecker}
      />
    );

    const editBtn = screen.getByTestId("edit-narrative-btn");
    fireEvent.click(editBtn);

    const textarea = screen.getByTestId("narrative-textarea");
    fireEvent.change(textarea, { target: { value: "Updated assessment with checker edits." } });

    fireEvent.click(editBtn); // Done editing
    expect(screen.getByText("[CHECKER EDITED CONTENT]:")).toBeDefined();
  });

  it("executes approval action and affixes exact stamp carrying dual identities", () => {
    const verifiedFields = [
      {
        id: "f1",
        field_name: "t_actual",
        value: "8.2",
        unit: "mm",
        confidence: 0.98,
        is_verified: true,
        requires_verification: false,
        page: 1,
        imagePath: "scan.pdf",
      },
    ];

    const citations = [
      {
        id: "c1",
        doc_id: "KB-API-570",
        title: "Piping Code",
        clause_or_section: "7.1.2",
        claim_text: "Formula adheres to standard",
        is_cited: true,
      },
    ];

    const onApprove = vi.fn();

    render(
      <ReviewApprovePanel
        deliverableId="DELIV-TEST-101"
        title="TECHNICAL APPROVAL NOTE"
        subject="Column C-101"
        maker={mockMaker}
        checker={mockChecker}
        currentUser={mockChecker}
        initialFields={verifiedFields}
        initialCitations={citations}
        onApproveSuccess={onApprove}
      />
    );

    const approveBtn = screen.getByTestId("approve-btn") as HTMLButtonElement;
    expect(approveBtn.disabled).toBe(false);

    fireEvent.click(approveBtn);

    expect(screen.getByTestId("approval-stamp-box")).toBeDefined();
    expect(screen.getByText(/APPROVED BY: P. V. Kulkarni/)).toBeDefined();
    expect(screen.getByText(/PREPARED BY: A. Sharma/)).toBeDefined();
    expect(onApprove).toHaveBeenCalledWith(
      expect.objectContaining({
        action: "APPROVED",
        maker: mockMaker,
        checker: mockChecker,
      })
    );
  });

  it("handles rejection modal workflow requiring mandatory written reason", () => {
    const onReject = vi.fn();

    render(
      <ReviewApprovePanel
        deliverableId="DELIV-TEST-101"
        title="TECHNICAL APPROVAL NOTE"
        subject="Column C-101"
        maker={mockMaker}
        checker={mockChecker}
        currentUser={mockChecker}
        onRejectSuccess={onReject}
      />
    );

    const rejectBtn = screen.getByTestId("reject-btn");
    fireEvent.click(rejectBtn);

    expect(screen.getByTestId("rejection-modal")).toBeDefined();

    const submitBtn = screen.getByTestId("submit-rejection-btn") as HTMLButtonElement;
    expect(submitBtn.disabled).toBe(true); // Disabled when reason empty!

    const reasonInput = screen.getByTestId("rejection-reason-input");
    fireEvent.change(reasonInput, { target: { value: "Calculated wall thickness requires secondary UT scan verification." } });

    expect(submitBtn.disabled).toBe(false);
    fireEvent.click(submitBtn);

    expect(onReject).toHaveBeenCalledWith(
      expect.objectContaining({
        action: "REJECTED",
        reason: "Calculated wall thickness requires secondary UT scan verification.",
      })
    );
  });

  it("renders read-only terminal state for concurrent accesses", () => {
    render(
      <ReviewApprovePanel
        deliverableId="DELIV-TEST-101"
        title="TECHNICAL APPROVAL NOTE"
        subject="Column C-101"
        maker={mockMaker}
        checker={mockChecker}
        currentUser={mockChecker}
        isConcurrent={true}
      />
    );

    expect(screen.getByText(/APPROVED & SIGNED/)).toBeDefined();
    expect(screen.getByText(/This deliverable was approved by P. V. Kulkarni/)).toBeDefined();
  });
});
