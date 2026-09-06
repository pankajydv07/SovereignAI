/** Pure UI-local state types. Zero IPC entities belong here. */

export type UIStateKind = "default" | "empty" | "loading" | "error" | "degraded";

export type UIState =
  | { type: "default" }
  | { type: "empty"; actionLabel?: string; suggestion?: string }
  | { type: "loading"; stage: string; elapsedMs: number }
  | { type: "error"; message: string; remedyLabel: string }
  | { type: "degraded"; message: string; remedyLabel: string };
