import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ApprovalCard } from "../ApprovalCard";

describe("ApprovalCard Component", () => {
  it("renders exact command diff, pattern scope text, and handles permission responses", () => {
    const onRespond = vi.fn();

    render(
      <ApprovalCard
        requestId="req_123"
        tool="fs_write"
        sideEffect="write"
        resourcePattern="docs/**"
        description="Write new documentation file"
        diffOrCommand="+ new line added"
        onRespond={onRespond}
      />
    );

    expect(screen.getByTestId("approval-card")).toBeDefined();
    expect(screen.getByTestId("pattern-scope").textContent).toContain("docs/**");
    expect(screen.getByTestId("diff-command-pre").textContent).toContain("+ new line added");

    fireEvent.click(screen.getByTestId("allow-once-btn"));
    expect(onRespond).toHaveBeenCalledWith("req_123", "allow_once", "docs/**");

    fireEvent.click(screen.getByTestId("always-allow-btn"));
    expect(onRespond).toHaveBeenCalledWith("req_123", "always_allow", "docs/**");

    fireEvent.click(screen.getByTestId("deny-btn"));
    expect(onRespond).toHaveBeenCalledWith("req_123", "deny");
  });
});
