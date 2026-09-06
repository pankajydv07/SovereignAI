import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { PlanCard, PlanStepItem } from "../PlanCard";

describe("PlanCard Component", () => {
  it("renders steps, side-effect badges, and handles action triggers", () => {
    const steps: PlanStepItem[] = [
      {
        stepIndex: 1,
        description: "Read documentation",
        tool: "fs_read",
        sideEffect: "read",
        requiresApproval: false,
      },
      {
        stepIndex: 2,
        description: "Write notes",
        tool: "fs_write",
        sideEffect: "write",
        requiresApproval: true,
      },
    ];

    const onRun = vi.fn();
    const onCancel = vi.fn();

    render(
      <PlanCard
        steps={steps}
        onRunPlan={onRun}
        onCancelPlan={onCancel}
        dependencyWarnings={["Step 2 depends on Step 1"]}
      />
    );

    expect(screen.getByTestId("plan-card")).toBeDefined();
    expect(screen.getByText("Read documentation")).toBeDefined();
    expect(screen.getByText("Write notes")).toBeDefined();
    expect(screen.getByText("ASK")).toBeDefined();
    expect(screen.getByTestId("dependency-warning")).toBeDefined();

    fireEvent.click(screen.getByTestId("run-plan-btn"));
    expect(onRun).toHaveBeenCalledOnce();

    fireEvent.click(screen.getByTestId("cancel-plan-btn"));
    expect(onCancel).toHaveBeenCalledOnce();
  });
});
