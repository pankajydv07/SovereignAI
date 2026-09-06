import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ModelRoster, ModelRosterItem } from "../ModelRoster";

describe("ModelRoster Component", () => {
  it("renders installed model roster with capability chips, VRAM vs total RAM, and residency badges", () => {
    const mockModels: ModelRosterItem[] = [
      {
        tag: "qwen2.5-coder:32b",
        digest: "sha256:abc12345",
        parameterSize: "32B",
        quantizationLevel: "Q4_K_M",
        contextLength: 32768,
        supportsVision: false,
        supportsThinking: true,
        supportsTools: true,
        family: "qwen2",
        sizeVram: "18.0 GB",
        sizeTotal: "20.0 GB",
        isResident: true,
      },
    ];

    const onSelect = vi.fn();

    render(<ModelRoster models={mockModels} onSelectModel={onSelect} />);

    expect(screen.getByTestId("model-roster-panel")).toBeDefined();
    expect(screen.getByText("qwen2.5-coder:32b")).toBeDefined();
    expect(screen.getByTestId("cap-tools-qwen2.5-coder:32b")).toBeDefined();
    expect(screen.getByTestId("cap-thinking-qwen2.5-coder:32b")).toBeDefined();

    expect(screen.getByText("18.0 GB")).toBeDefined();
    expect(screen.getByText("20.0 GB")).toBeDefined();
    expect(screen.getByTestId("model-residency-badge-qwen2.5-coder:32b").textContent).toBe("Resident");

    fireEvent.click(screen.getByTestId("model-row-0"));
    expect(onSelect).toHaveBeenCalledWith("qwen2.5-coder:32b");
  });
});
