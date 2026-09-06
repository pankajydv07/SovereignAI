import { SessionEvent, SessionEventSchema, SessionInfo, SessionInfoSchema } from "../protocol";
import { UIState } from "../types/ui";
import { z } from "zod";

export interface SessionState {
  sessions: SessionInfo[];
  activeSessionId: string | null;
  activeEvents: SessionEvent[];
  uiState: UIState;
}

export type SessionAction =
  | { type: "SET_LOADING"; stage: string; elapsedMs: number }
  | { type: "SET_SESSIONS"; payload: unknown }
  | { type: "ADD_SESSION"; payload: unknown }
  | { type: "SET_ACTIVE_SESSION"; id: string | null }
  | { type: "SET_SESSION_LOADED"; session: unknown; events: unknown }
  | { type: "UPDATE_SESSION_STATUS"; id: string; status: string }
  | { type: "SET_ERROR"; message: string; remedyLabel: string }
  | { type: "SET_DEGRADED"; message: string; remedyLabel: string };

export const initialSessionState: SessionState = {
  sessions: [],
  activeSessionId: null,
  activeEvents: [],
  uiState: { type: "loading", stage: "connecting to core...", elapsedMs: 0 },
};

export function sessionReducer(state: SessionState, action: SessionAction): SessionState {
  switch (action.type) {
    case "SET_LOADING":
      return {
        ...state,
        uiState: { type: "loading", stage: action.stage, elapsedMs: action.elapsedMs },
      };

    case "SET_SESSIONS": {
      const parsed = z.array(SessionInfoSchema).safeParse(action.payload);
      if (!parsed.success) {
        return {
          ...state,
          uiState: {
            type: "error",
            message: `Protocol validation error: ${parsed.error.message}`,
            remedyLabel: "Retry Sessions",
          },
        };
      }
      const sessions = parsed.data;
      if (sessions.length === 0) {
        return {
          ...state,
          sessions: [],
          uiState: {
            type: "empty",
            actionLabel: "Create New Session",
            suggestion: "Start a new session to inspect documents",
          },
        };
      }
      return {
        ...state,
        sessions,
        uiState: { type: "default" },
      };
    }

    case "ADD_SESSION": {
      const parsed = SessionInfoSchema.safeParse(action.payload);
      if (!parsed.success) {
        return state;
      }
      const newSess = parsed.data;
      const updated = [
        newSess,
        ...state.sessions.filter((s) => s.sessionId !== newSess.sessionId),
      ];
      return {
        ...state,
        sessions: updated,
        activeSessionId: newSess.sessionId,
        uiState: { type: "default" },
      };
    }

    case "SET_ACTIVE_SESSION":
      return { ...state, activeSessionId: action.id };

    case "SET_SESSION_LOADED": {
      const parsedSession = SessionInfoSchema.safeParse(action.session);
      const parsedEvents = z.array(SessionEventSchema).safeParse(action.events);

      if (!parsedSession.success || !parsedEvents.success) {
        return {
          ...state,
          uiState: {
            type: "error",
            message: "Failed to parse session transcript data",
            remedyLabel: "Reload Session",
          },
        };
      }

      return {
        ...state,
        activeSessionId: parsedSession.data.sessionId,
        activeEvents: parsedEvents.data,
        uiState: { type: "default" },
      };
    }

    case "UPDATE_SESSION_STATUS": {
      const updated = state.sessions.map((s) =>
        s.sessionId === action.id ? { ...s, status: action.status } : s
      );
      return { ...state, sessions: updated };
    }

    case "SET_ERROR":
      return {
        ...state,
        uiState: { type: "error", message: action.message, remedyLabel: action.remedyLabel },
      };

    case "SET_DEGRADED":
      return {
        ...state,
        uiState: { type: "degraded", message: action.message, remedyLabel: action.remedyLabel },
      };

    default:
      return state;
  }
}
