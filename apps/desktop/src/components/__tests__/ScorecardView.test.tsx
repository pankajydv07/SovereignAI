import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ScorecardView, ScorecardModelPriors, ScorecardMetadata } from "../ScorecardView";

describe("ScorecardView Component", () => {
  it("renders scorecard view with hardware stamp, task class bars, and tabular scores", () => {
    const mockMetadata: ScorecardMetadata = {
      gpu: "NVIDIA GeForce RTX 4090",
      date: "2026-09-06",
      suite: "eval suite v1",
    };

    const mockModelsPriors: ScorecardModelPriors[] = [
      {
        modelTag: "qwen3-coder:30b",
        priors: {
          code_generate: 0.98,
          code_debug: 1.0,
        },
      },
      {
        modelTag: "qwen3:30b",
        priors: {
          code_generate: 0.82,
          code_debug: 0.88,
        },
      },
    ];

    render(
      <ScorecardView
        metadata={mockMetadata}
        modelsPriors={mockModelsPriors}
        taskClasses={["code_generate", "code_debug"]}
      />
    );

    expect(screen.getByTestId("scorecard-view")).toBeDefined();

    // Stamp header assertion
    const stamp = screen.getByTestId("scorecard-stamp");
    expect(stamp.textContent).toContain("measured on NVIDIA GeForce RTX 4090 · 2026-09-06 · eval suite v1");

    // Task class groups
    expect(screen.getByTestId("task-class-group-code_generate")).toBeDefined();
    expect(screen.getByTestId("task-class-group-code_debug")).toBeDefined();

    // Model bars and tabular scores
    expect(screen.getByTestId("model-bar-code_generate-qwen3-coder:30b")).toBeDefined();
    expect(screen.getByText("0.98")).toBeDefined();
    expect(screen.getByText("1.00")).toBeDefined();
  });
});
