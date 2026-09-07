import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { RoutingBadge, RoutingDecisionPayload } from "../RoutingBadge";

describe("RoutingBadge Component", () => {
  it("renders monospace 11px routing badge and displays MANUAL OVERRIDE badge state when user forced model", () => {
    render(
      <RoutingBadge
        role="coder"
        model="qwen3-coder:30b"
        confidence={0.98}
        latencyMs={28}
        isManualOverride={true}
      />
    );

    expect(screen.getByTestId("routing-badge-button")).toBeDefined();
    expect(screen.getByText("qwen3-coder:30b")).toBeDefined();
    expect(screen.getByTestId("manual-override-badge").textContent).toContain("MANUAL OVERRIDE");
  });

  it("toggles 420px routing popover on click with winner left border and rejection reasons", () => {
    const mockDecision: RoutingDecisionPayload = {
      taskClass: "code_generate",
      selectedModelTag: "qwen3-coder:30b",
      fallbackModelTag: "qwen3:30b",
      confidence: 0.96,
      routingLatencyMs: 14.2,
      isManualOverride: false,
      featureVector: {
        hasImage: false,
        codeFences: 1,
        estimatedTokens: 250,
      },
      candidates: [
        {
          modelTag: "qwen3-coder:30b",
          qualityPrior: 0.95,
          vramFit: 1.0,
          latencyScore: 0.9,
          swapPenalty: 0.0,
          totalScore: 0.88,
          isWinner: true,
          rejectionReason: null,
        },
        {
          modelTag: "qwen3:30b",
          qualityPrior: 0.80,
          vramFit: 0.8,
          latencyScore: 0.7,
          swapPenalty: 1.0,
          totalScore: 0.45,
          isWinner: false,
          rejectionReason: "not resident, swap cost 6.1s",
        },
      ],
    };

    render(
      <RoutingBadge
        role="coder"
        model="qwen3-coder:30b"
        decision={mockDecision}
      />
    );

    expect(screen.getByTestId("confidence-val").textContent).toBe("CONFIDENT");

    // Click badge to toggle popover
    fireEvent.click(screen.getByTestId("routing-badge-button"));

    expect(screen.getByTestId("routing-popover")).toBeDefined();
    expect(screen.getByTestId("feature-vector-box")).toBeDefined();

    // Winner assertion
    expect(screen.getByTestId("winner-tag-qwen3-coder:30b")).toBeDefined();
    const winnerRow = screen.getByTestId("candidate-row-0");
    expect(winnerRow.className).toContain("border-l-[3px] border-l-[#10B981]");

    // Loser rejection reason assertion
    const loserReason = screen.getByTestId("rejection-reason-qwen3:30b");
    expect(loserReason.textContent).toBe("not resident, swap cost 6.1s");
  });
});
