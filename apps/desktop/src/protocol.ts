// GENERATED FILE — DO NOT EDIT MANUALLY
// Source: packages/protocol/schema/*.json
// Run `make protocol` to regenerate.

export interface ProtocolMessage {
  jsonrpc: "2.0";
  id?: string;
  method: string;
  params: Record<string, unknown>;
}
