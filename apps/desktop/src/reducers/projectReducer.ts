import { ProjectInfo, ProjectInfoSchema } from "../protocol";
import { UIState } from "../types/ui";
import { z } from "zod";

export interface ProjectState {
  projects: ProjectInfo[];
  activeProjectId: string | null;
  uiState: UIState;
}

export type ProjectAction =
  | { type: "SET_LOADING"; stage: string; elapsedMs: number }
  | { type: "SET_PROJECTS"; payload: unknown }
  | { type: "ADD_PROJECT"; payload: unknown }
  | { type: "REMOVE_PROJECT"; id: string }
  | { type: "SET_ACTIVE_PROJECT"; id: string | null }
  | { type: "SET_ERROR"; message: string; remedyLabel: string }
  | { type: "SET_DEGRADED"; message: string; remedyLabel: string };

export const initialProjectState: ProjectState = {
  projects: [],
  activeProjectId: null,
  uiState: { type: "loading", stage: "initializing projects...", elapsedMs: 0 },
};

export function projectReducer(state: ProjectState, action: ProjectAction): ProjectState {
  switch (action.type) {
    case "SET_LOADING":
      return {
        ...state,
        uiState: { type: "loading", stage: action.stage, elapsedMs: action.elapsedMs },
      };

    case "SET_PROJECTS": {
      const parsed = z.array(ProjectInfoSchema).safeParse(action.payload);
      if (!parsed.success) {
        return {
          ...state,
          uiState: {
            type: "error",
            message: `Protocol schema mismatch: ${parsed.error.message}`,
            remedyLabel: "Retry Projects Load",
          },
        };
      }
      const projects = parsed.data;
      if (projects.length === 0) {
        return {
          ...state,
          projects: [],
          uiState: { type: "empty", actionLabel: "Open Project Folder", suggestion: "Select a folder to begin" },
        };
      }
      return {
        ...state,
        projects,
        uiState: { type: "default" },
      };
    }

    case "ADD_PROJECT": {
      const parsed = ProjectInfoSchema.safeParse(action.payload);
      if (!parsed.success) {
        return state;
      }
      const newProj = parsed.data;
      const filtered = state.projects.filter((p) => p.id !== newProj.id && p.path !== newProj.path);
      return {
        ...state,
        projects: [newProj, ...filtered],
        activeProjectId: newProj.id,
        uiState: { type: "default" },
      };
    }

    case "REMOVE_PROJECT": {
      const updated = state.projects.filter((p) => p.id !== action.id);
      return {
        ...state,
        projects: updated,
        activeProjectId: state.activeProjectId === action.id ? null : state.activeProjectId,
        uiState: updated.length === 0 ? { type: "empty", actionLabel: "Open Project Folder" } : { type: "default" },
      };
    }

    case "SET_ACTIVE_PROJECT":
      return { ...state, activeProjectId: action.id };

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
