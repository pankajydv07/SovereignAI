import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { GpuAllocationBar, LoadedModelItem, UnloadedModelItem } from "../GpuAllocationBar";

describe("GpuAllocationBar Component", () => {
  it("computes exact VRAM segment percentage widths and renders solid resident models plus free VRAM", () => {
    const totalVramBytes = 24 * 1024 * 1024 * 1024; // 24 GB
    const loadedModels: LoadedModelItem[] = [
      {
        modelTag: "qwen3-coder:30b",
        sizeVramBytes: 12 * 1024 * 1024 * 1024, // 12 GB (50%)
      },
      {
        modelTag: "qwen2.5vl:7b",
        sizeVramBytes: 6 * 1024 * 1024 * 1024, // 6 GB (25%)
      },
    ];

    const unloadedModels: UnloadedModelItem[] = [
      { modelTag: "qwen3:30b" },
    ];

    render(
      <GpuAllocationBar
        loadedModels={loadedModels}
        unloadedModels={unloadedModels}
        totalVramBytes={totalVramBytes}
      />
    );

    expect(screen.getByTestId("gpu-allocation-bar-container")).toBeDefined();
    expect(screen.getByTestId("vram-summary-text").textContent).toContain("18.0 GB / 24.0 GB (75.0%)");

    // Exact segment width assertions
    const seg1 = screen.getByTestId("vram-segment-qwen3-coder:30b");
    expect(seg1.style.width).toBe("50%");

    const seg2 = screen.getByTestId("vram-segment-qwen2.5vl:7b");
    expect(seg2.style.width).toBe("25%");

    const freeSeg = screen.getByTestId("vram-segment-free");
    expect(freeSeg.style.width).toBe("25%");

    // Transition class and motion-reduce assertion
    expect(seg1.className).toContain("transition-all duration-400 motion-reduce:transition-none");

    // Unloaded models chip row assertion
    expect(screen.getByTestId("unloaded-models-row")).toBeDefined();
    expect(screen.getByTestId("unloaded-chip-qwen3:30b").textContent).toContain("qwen3:30b — not loaded");
  });
});
