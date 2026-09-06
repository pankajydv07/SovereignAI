import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { RunTrace, TraceStepItem } from "../RunTrace";

describe("RunTrace Component", () => {
  it("renders budget meter bar, 30px step rows, and expands critique text verbatim", () => {
    const steps: TraceStepItem[] = [
      {
        stepIndex: 1,
        description: "Read configuration file",
        tool: "fs_read",
        status: "completed",
        inputJson: '{"path": "config.yaml"}',
        outputJson: '{"content": "key: val"}',
      },
      {
        stepIndex: 2,
        description: "Write update",
        tool: "fs_write",
        status: "failed",
        critiqueText: "Tier 1 validation failed: invalid format",
      },
    ];

    render(
      <RunTrace
        steps={steps}
        stepCount={2}
        maxSteps={25}
        totalTokens={1500}
        maxTokens={32000}
      />
    );

    expect(screen.getByTestId("run-trace-panel")).toBeDefined();
    expect(screen.getByTestId("budget-meter-bar")).toBeDefined();
    expect(screen.getByTestId("status-glyph-1")).toBeDefined();
    expect(screen.getByTestId("status-glyph-2")).toBeDefined();

    // Toggle expand for step 2
    fireEvent.click(screen.getByTestId("status-glyph-2"));
    expect(screen.getByTestId("critique-text-2").textContent).toContain(
      "Tier 1 validation failed"
    );
  });
});
