// GENERATED FILE — DO NOT EDIT MANUALLY
// Source: packages/protocol/schema/*.json
// Run `make protocol` to regenerate.

import { z } from "zod";

export const PROTOCOL_VERSION = "2026-03-01";

export const ProtocolMessageSchema = z.object({
  jsonrpc: z.literal("2.0"),
  id: z.string().optional(),
  method: z.string(),
  params: z.record(z.string(), z.unknown()).default({}),
});
export type ProtocolMessage = z.infer<typeof ProtocolMessageSchema>;

export const CoreStateSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("connecting") }),
  z.object({
    type: z.literal("ready"),
    version: z.string(),
    protocol_version: z.string(),
  }),
  z.object({ type: z.literal("restarting"), attempt: z.number().int() }),
  z.object({ type: z.literal("error"), message: z.string() }),
  z.object({
    type: z.literal("failed"),
    reason: z.string(),
    stderr_tail: z.array(z.string()).optional(),
  }),
  z.object({ type: z.literal("disconnected") }),
]);
export type CoreState = z.infer<typeof CoreStateSchema>;

export const InitializeParamsSchema = z.object({
  protocolVersion: z.string(),
  capabilities: z.array(z.string()),
});
export type InitializeParams = z.infer<typeof InitializeParamsSchema>;

export const InitializeResultSchema = z.object({
  protocolVersion: z.string(),
  capabilities: z.array(z.string()),
});
export type InitializeResult = z.infer<typeof InitializeResultSchema>;

export const ToolCallStatusSchema = z.enum(["pending", "in_progress", "completed", "failed"]);
export type ToolCallStatus = z.infer<typeof ToolCallStatusSchema>;

export const ToolKindSchema = z.enum([
  "read",
  "edit",
  "delete",
  "move",
  "search",
  "execute",
  "think",
  "fetch",
  "other",
]);
export type ToolKind = z.infer<typeof ToolKindSchema>;

export const StopReasonSchema = z.enum([
  "end_turn",
  "max_tokens",
  "max_turn_requests",
  "refusal",
  "cancelled",
]);
export type StopReason = z.infer<typeof StopReasonSchema>;

export const ToolCallUpdateSchema = z.object({
  toolCallId: z.string(),
  name: z.string(),
  kind: ToolKindSchema,
  status: ToolCallStatusSchema,
  input: z.record(z.string(), z.unknown()).optional(),
  output: z.record(z.string(), z.unknown()).optional(),
  error: z.string().optional(),
});
export type ToolCallUpdate = z.infer<typeof ToolCallUpdateSchema>;

export const PermissionOptionSchema = z.enum([
  "allow_once",
  "allow_session",
  "always_allow",
  "deny",
]);
export type PermissionOption = z.infer<typeof PermissionOptionSchema>;

export const DiffContentSchema = z.object({
  path: z.string(),
  oldText: z.string().optional(),
  newText: z.string(),
});
export type DiffContent = z.infer<typeof DiffContentSchema>;

export const TerminalContentSchema = z.object({
  terminalId: z.string(),
  data: z.string(),
});
export type TerminalContent = z.infer<typeof TerminalContentSchema>;

export const PermissionRequestParamsSchema = z.object({
  requestId: z.string(),
  tool: z.string(),
  sideEffect: z.string(),
  description: z.string(),
  options: z.array(PermissionOptionSchema),
  diff: DiffContentSchema.optional(),
});
export type PermissionRequestParams = z.infer<typeof PermissionRequestParamsSchema>;

export const PermissionResponseParamsSchema = z.object({
  requestId: z.string(),
  selectedOption: PermissionOptionSchema,
});
export type PermissionResponseParams = z.infer<typeof PermissionResponseParamsSchema>;

export const ProvenanceMetaSchema = z.object({
  field: z.string(),
  confidence: z.number(),
  page: z.number().int(),
  bbox: z.tuple([z.number(), z.number(), z.number(), z.number()]),
  extractor: z.string(),
});
export type ProvenanceMeta = z.infer<typeof ProvenanceMetaSchema>;

export const MakerCheckerMetaSchema = z.object({
  maker: z.string(),
  checker: z.string().optional(),
  status: z.enum(["pending", "approved", "rejected"]),
  timestamp: z.string(),
});
export type MakerCheckerMeta = z.infer<typeof MakerCheckerMetaSchema>;

export const DeliverableMetaSchema = z.object({
  type: z.enum([
    "approval_note",
    "inspection_summary",
    "review_deck",
    "cost_sheet",
    "engineering_calculation",
  ]),
  draft: z.boolean(),
  parameters: z.record(z.string(), z.unknown()),
  citations: z.array(z.string()).default([]),
});
export type DeliverableMeta = z.infer<typeof DeliverableMetaSchema>;

export const SwarajMetaSchema = z.object({
  provenance: ProvenanceMetaSchema.optional(),
  makerChecker: MakerCheckerMetaSchema.optional(),
  deliverable: DeliverableMetaSchema.optional(),
});
export type SwarajMeta = z.infer<typeof SwarajMetaSchema>;

export const PlanStepSchema = z.object({
  stepIndex: z.number().int(),
  description: z.string(),
  tool: z.string().optional(),
  sideEffect: z.string().optional(),
  requiresApproval: z.boolean().optional(),
});
export type PlanStep = z.infer<typeof PlanStepSchema>;

export const ToolCallUpdatePayloadSchema = z.object({
  type: z.literal("tool_call"),
  toolCall: ToolCallUpdateSchema,
});

export const PlanUpdatePayloadSchema = z.object({
  type: z.literal("plan"),
  steps: z.array(PlanStepSchema),
});

export const DiffUpdatePayloadSchema = z.object({
  type: z.literal("diff"),
  diff: DiffContentSchema,
});

export const TerminalUpdatePayloadSchema = z.object({
  type: z.literal("terminal"),
  terminal: TerminalContentSchema,
});

export const StateChangeUpdatePayloadSchema = z.object({
  type: z.literal("state_change"),
  state: z.string(),
});

export const SessionUpdatePayloadSchema = z.discriminatedUnion("type", [
  ToolCallUpdatePayloadSchema,
  PlanUpdatePayloadSchema,
  DiffUpdatePayloadSchema,
  TerminalUpdatePayloadSchema,
  StateChangeUpdatePayloadSchema,
]);
export type SessionUpdatePayload = z.infer<typeof SessionUpdatePayloadSchema>;

export const SessionUpdateNotificationSchema = z.object({
  sessionId: z.string(),
  update: SessionUpdatePayloadSchema,
  meta: SwarajMetaSchema.optional(),
});
export type SessionUpdateNotification = z.infer<typeof SessionUpdateNotificationSchema>;
