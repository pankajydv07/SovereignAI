import assert from "node:assert";
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

function runTests(): void {
  console.log("Running TypeScript Protocol Cross-Language Tests...");

  // Test 1: initialize_request.json
  const rawInit = readFixture("initialize_request.json");
  const parsedInit = ProtocolMessageSchema.parse(rawInit);
  assert.deepStrictEqual(parsedInit, rawInit);
  console.log("  PASS: initialize_request.json round-trip");

  // Test 2: session_update_tool_call.json
  const rawTool = readFixture("session_update_tool_call.json");
  const parsedTool = SessionUpdateNotificationSchema.parse(rawTool);
  assert.deepStrictEqual(parsedTool, rawTool);
  console.log("  PASS: session_update_tool_call.json round-trip");

  // Test 3: permission_request.json
  const rawPerm = readFixture("permission_request.json");
  const parsedPerm = PermissionRequestParamsSchema.parse(rawPerm);
  assert.deepStrictEqual(parsedPerm, rawPerm);
  console.log("  PASS: permission_request.json round-trip");

  // Test 4: diff_content_absent_optional.json
  const rawDiff = readFixture("diff_content_absent_optional.json") as Record<string, unknown>;
  const parsedDiff = DiffContentSchema.parse(rawDiff);
  assert.strictEqual(parsedDiff.oldText, undefined);
  assert.deepStrictEqual(parsedDiff, rawDiff);
  assert.strictEqual("oldText" in parsedDiff, false);
  console.log("  PASS: diff_content_absent_optional.json absent optional property");

  // Test 5: swaraj_meta_provenance.json
  const rawMeta = readFixture("swaraj_meta_provenance.json");
  const parsedMeta = SessionUpdateNotificationSchema.parse(rawMeta);
  assert.deepStrictEqual(parsedMeta, rawMeta);
  assert.strictEqual(parsedMeta.meta?.provenance?.confidence, 0.98);
  console.log("  PASS: swaraj_meta_provenance.json SwarajMeta preservation");

  // Test 6: Unknown variant fails loudly
  const invalidData = {
    sessionId: "sess-unknown",
    update: {
      type: "non_existent_update_variant",
      foo: "bar",
    },
  };

  assert.throws(
    () => {
      SessionUpdateNotificationSchema.parse(invalidData);
    },
    (err: Error) => {
      return err.name === "ZodError";
    }
  );
  console.log("  PASS: unknown variant fails loudly with ZodError");

  console.log("\nAll TypeScript protocol tests passed successfully!");
}

runTests();
