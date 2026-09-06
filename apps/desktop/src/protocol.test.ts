import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  DiffContentSchema,
  PermissionRequestParamsSchema,
  ProtocolMessageSchema,
  SessionUpdateNotificationSchema,
} from "./protocol.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const FIXTURES_DIR = resolve(__dirname, "../../../packages/protocol/fixtures");

function readFixture(filename: string): unknown {
  const content = readFileSync(resolve(FIXTURES_DIR, filename), "utf-8");
  return JSON.parse(content);
}

describe("TypeScript Protocol Cross-Language Tests", () => {
  it("validates initialize_request.json round-trip", () => {
    const rawInit = readFixture("initialize_request.json");
    const parsedInit = ProtocolMessageSchema.parse(rawInit);
    expect(parsedInit).toEqual(rawInit);
  });

  it("validates session_update_tool_call.json round-trip", () => {
    const rawTool = readFixture("session_update_tool_call.json");
    const parsedTool = SessionUpdateNotificationSchema.parse(rawTool);
    expect(parsedTool).toEqual(rawTool);
  });

  it("validates permission_request.json round-trip", () => {
    const rawPerm = readFixture("permission_request.json");
    const parsedPerm = PermissionRequestParamsSchema.parse(rawPerm);
    expect(parsedPerm).toEqual(rawPerm);
  });

  it("validates diff_content_absent_optional.json", () => {
    const rawDiff = readFixture("diff_content_absent_optional.json") as Record<string, unknown>;
    const parsedDiff = DiffContentSchema.parse(rawDiff);
    expect(parsedDiff.oldText).toBeUndefined();
    expect(parsedDiff).toEqual(rawDiff);
  });

  it("validates swaraj_meta_provenance.json preservation", () => {
    const rawMeta = readFixture("swaraj_meta_provenance.json");
    const parsedMeta = SessionUpdateNotificationSchema.parse(rawMeta);
    expect(parsedMeta).toEqual(rawMeta);
    expect(parsedMeta.meta?.provenance?.confidence).toBe(0.98);
  });

  it("fails loudly with ZodError on unknown variants", () => {
    const invalidData = {
      sessionId: "sess-unknown",
      update: {
        type: "non_existent_update_variant",
        foo: "bar",
      },
    };
    expect(() => SessionUpdateNotificationSchema.parse(invalidData)).toThrow();
  });
});
