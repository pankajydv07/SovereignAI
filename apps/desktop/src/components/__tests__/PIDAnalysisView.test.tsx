import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PIDAnalysisView } from "../PIDAnalysisView";

describe("PIDAnalysisView Component", () => {
  it("renders drawing canvas and honest UI boundary statement", () => {
    render(<PIDAnalysisView />);

    expect(screen.getByTestId("pid-analysis-view")).toBeDefined();
    expect(screen.getByTestId("pid-drawing-canvas")).toBeDefined();
    expect(screen.getByTestId("honest-disclaimer-banner")).toBeDefined();
    expect(
      screen.getByText(
        /Note: P&ID analysis performs symbol detection and tag extraction only. It does NOT reconstruct drawing topology, trace pipe lines, or validate control-loop logic./
      )
    ).toBeDefined();
  });

  it("renders 11 Roboflow symbol inventory classes and counts", () => {
    render(<PIDAnalysisView />);

    expect(screen.getByText(/1\. Symbol Inventory/)).toBeDefined();
    expect(screen.getByText("instrument_tag")).toBeDefined();
    expect(screen.getByText("instrument_dcs")).toBeDefined();
    expect(screen.getByText("gate_valve")).toBeDefined();
    expect(screen.getByText("control_valve")).toBeDefined();
    expect(screen.getByText("pump")).toBeDefined();
  });

  it("renders master equipment register reconciliation table with planted discrepancy", () => {
    render(<PIDAnalysisView />);

    expect(screen.getByText("2. Master Register Reconciliation")).toBeDefined();

    // Matched items
    expect(screen.getByText("PT-101")).toBeDefined();
    expect(screen.getByText("TI-202")).toBeDefined();
    expect(screen.getByText("FIC-204A")).toBeDefined();

    // Discrepancy item PI-108
    expect(screen.getByText("PI-108")).toBeDefined();
    expect(screen.getByText(/Missing from Master Equipment Register/)).toBeDefined();

    // Unreadable item
    expect(screen.getByText("[UNREADABLE REGION]")).toBeDefined();
    expect(screen.getByText(/OCR crop unreadable · requires human review/)).toBeDefined();
  });

  it("ensures unreadable region displays confidence as null", () => {
    render(<PIDAnalysisView />);

    const unreadableTag = screen.getByText("[UNREADABLE REGION]");
    expect(unreadableTag).toBeDefined();

    // Spec requirement 6: confidence is null for unreadable regions
    expect(screen.getByText("null")).toBeDefined();
  });

  it("supports annotated overlay toggle interaction", () => {
    render(<PIDAnalysisView />);

    const toggleBtn = screen.getByTestId("toggle-overlay-btn");
    expect(toggleBtn.textContent).toContain("Annotated Overlay ON");

    fireEvent.click(toggleBtn);
    expect(toggleBtn.textContent).toContain("Annotated Overlay OFF");
  });
});
