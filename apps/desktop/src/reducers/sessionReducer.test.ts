import { describe, it, expect } from "vitest";
import { sessionReducer, initialSessionState } from "./sessionReducer";
import { SessionEvent, SessionInfo } from "../protocol";

describe("sessionReducer", () => {
  it("handles loading state with stage label and elapsed time", () => {
    const next = sessionReducer(initialSessionState, {
      type: "SET_LOADING",
      stage: "fetching session list...",
      elapsedMs: 120,
    });
    expect(next.uiState).toEqual({
      type: "loading",
      stage: "fetching session list...",
      elapsedMs: 120,
    });
  });

  it("handles default and empty states when setting valid sessions", () => {
    const validSessions: SessionInfo[] = [
      {
        sessionId: "s1",
        projectId: "p1",
        title: "Session 1",
        status: "active",
        createdAtMs: 100,
        updatedAtMs: 200,
      },
    ];
    const defaultState = sessionReducer(initialSessionState, {
      type: "SET_SESSIONS",
      payload: validSessions,
    });
    expect(defaultState.uiState.type).toBe("default");
    expect(defaultState.sessions).toHaveLength(1);

    const emptyState = sessionReducer(initialSessionState, {
      type: "SET_SESSIONS",
      payload: [],
    });
    expect(emptyState.uiState.type).toBe("empty");
    expect(emptyState.sessions).toHaveLength(0);
  });

  it("handles error state on invalid Zod payload", () => {
    const invalidState = sessionReducer(initialSessionState, {
      type: "SET_SESSIONS",
      payload: "not an array",
    });
    expect(invalidState.uiState.type).toBe("error");
    if (invalidState.uiState.type === "error") {
      expect(invalidState.uiState.remedyLabel).toBe("Retry Sessions");
    }
  });

  it("handles SET_SESSION_LOADED with transcript events", () => {
    const session: SessionInfo = {
      sessionId: "s1",
      projectId: "p1",
      title: "Session 1",
      status: "active",
      createdAtMs: 100,
      updatedAtMs: 200,
    };
    const events: SessionEvent[] = [
      {
        sessionId: "s1",
        seq: 1,
        eventType: "session_created",
        payload: { title: "Session 1" },
        payloadVersion: 1,
        createdAtMs: 100,
      },
    ];

    const loadedState = sessionReducer(initialSessionState, {
      type: "SET_SESSION_LOADED",
      session,
      events,
    });

    expect(loadedState.activeSessionId).toBe("s1");
    expect(loadedState.activeEvents).toHaveLength(1);
    expect(loadedState.uiState.type).toBe("default");
  });
});
