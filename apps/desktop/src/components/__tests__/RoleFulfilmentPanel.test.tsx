import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { RoleFulfilmentPanel, RoleFulfilmentItem } from "../RoleFulfilmentPanel";

describe("RoleFulfilmentPanel Component", () => {
  it("renders satisfied status and consequence warnings for missing roles", () => {
    const mockFulfilment: RoleFulfilmentItem[] = [
      {
        role: "coder",
        satisfied: true,
        modelTag: "qwen2.5-coder:32b",
        residency: "RESIDENT",
        vramUsage: "18432.0 MB",
        consequence: null,
      },
      {
        role: "vision",
        satisfied: false,
        modelTag: "missing-vision-model:latest",
        residency: "MISSING",
        vramUsage: "0 MB",
        consequence: "Role 'vision' unavailable: 'missing-vision-model:latest' is not installed. Run: ollama pull missing-vision-model:latest",
      },
    ];

    const onRefresh = vi.fn();

    render(<RoleFulfilmentPanel fulfilment={mockFulfilment} onRefresh={onRefresh} />);

    expect(screen.getByTestId("role-fulfilment-panel")).toBeDefined();
    expect(screen.getByTestId("overall-status-badge").textContent).toContain("1 Unsatisfied");

    // Consequence banner assertion
    const banner = screen.getByTestId("consequence-banner-vision");
    expect(banner.textContent).toContain("ollama pull missing-vision-model:latest");

    // Role card assertions
    expect(screen.getByTestId("role-residency-coder").textContent).toBe("RESIDENT");
    expect(screen.getByTestId("role-residency-vision").textContent).toBe("MISSING");

    // Refresh button click
    fireEvent.click(screen.getByTestId("refresh-roles-btn"));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });
});
