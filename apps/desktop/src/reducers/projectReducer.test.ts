import { describe, it, expect } from "vitest";
import { projectReducer, initialProjectState } from "./projectReducer";
import { ProjectInfo } from "../protocol";

describe("projectReducer", () => {
  it("handles loading state with stage label and elapsed time", () => {
    const next = projectReducer(initialProjectState, {
      type: "SET_LOADING",
      stage: "loading workspace...",
      elapsedMs: 250,
    });
    expect(next.uiState).toEqual({
      type: "loading",
      stage: "loading workspace...",
      elapsedMs: 250,
    });
  });

  it("handles default and empty states when setting valid projects", () => {
    const validProjects: ProjectInfo[] = [
      {
        id: "p1",
        name: "Refinery Inspection",
        path: "/work/refinery",
        createdAtMs: 100,
        updatedAtMs: 200,
        exists: true,
      },
    ];
    const defaultState = projectReducer(initialProjectState, {
      type: "SET_PROJECTS",
      payload: validProjects,
    });
    expect(defaultState.uiState.type).toBe("default");
    expect(defaultState.projects).toHaveLength(1);

    const emptyState = projectReducer(initialProjectState, {
      type: "SET_PROJECTS",
      payload: [],
    });
    expect(emptyState.uiState.type).toBe("empty");
    expect(emptyState.projects).toHaveLength(0);
  });

  it("handles error state on invalid Zod payload", () => {
    const invalidState = projectReducer(initialProjectState, {
      type: "SET_PROJECTS",
      payload: [{ invalidKey: 123 }],
    });
    expect(invalidState.uiState.type).toBe("error");
    if (invalidState.uiState.type === "error") {
      expect(invalidState.uiState.remedyLabel).toBe("Retry Projects Load");
    }
  });

  it("handles degraded state when sidecar is unavailable", () => {
    const degradedState = projectReducer(initialProjectState, {
      type: "SET_DEGRADED",
      message: "Agent core unavailable — projects can be opened, sessions unavailable.",
      remedyLabel: "Retry Core",
    });
    expect(degradedState.uiState.type).toBe("degraded");
  });
});
