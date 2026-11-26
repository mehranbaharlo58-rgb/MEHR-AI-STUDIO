import test from "node:test";
import assert from "node:assert/strict";
import { validateDesktopBridgeEnvelope } from "../cloudflare/desktop-bridge-protocol.mjs";

const id = "abcdefghijklmnopqrstuv";
const base = {
  version: 1,
  room_id: id,
  session_id: "bcdefghijklmnopqrstuvw",
  sequence: 1,
  expires_at: 1100,
  kind: "session.stop",
  payload: { reason: "user_requested" },
};

test("accepts a well-formed short-lived stop envelope", () => {
  const result = validateDesktopBridgeEnvelope(base, { nowSeconds: 1000 });
  assert.equal(result.ok, true);
  assert.equal(result.envelope, base);
});

test("rejects unknown envelope fields instead of silently accepting them", () => {
  const result = validateDesktopBridgeEnvelope({ ...base, debug: true }, { nowSeconds: 1000 });
  assert.deepEqual(result, { ok: false, error: "invalid_envelope_shape" });
});

test("rejects replayed and non-monotonic sequence numbers", () => {
  const result = validateDesktopBridgeEnvelope(base, { nowSeconds: 1000, lastSequence: 1 });
  assert.deepEqual(result, { ok: false, error: "replayed_or_invalid_sequence" });
});

test("rejects expired and excessively long-lived messages", () => {
  assert.equal(validateDesktopBridgeEnvelope({ ...base, expires_at: 999 }, { nowSeconds: 1000 }).error, "invalid_expiry");
  assert.equal(validateDesktopBridgeEnvelope({ ...base, expires_at: 1061 }, { nowSeconds: 1000 }).error, "invalid_expiry");
});

test("requires local approval and bounded coordinates for action requests", () => {
  const valid = {
    ...base, kind: "action.request",
    payload: {
      action_id: "cdefghijklmnopqrstuvwx",
      action: "click",
      args: { x: 1200, y: 800, button: "left", clicks: 1 },
      reason: "Select the visible drawing tab",
      requires_local_approval: true,
    },
  };
  assert.equal(validateDesktopBridgeEnvelope(valid, { nowSeconds: 1000 }).ok, true);
  assert.equal(validateDesktopBridgeEnvelope({
    ...valid, payload: { ...valid.payload, requires_local_approval: false },
  }, { nowSeconds: 1000 }).error, "invalid_message_payload");
  assert.equal(validateDesktopBridgeEnvelope({
    ...valid, payload: { ...valid.payload, args: { x: 9000, y: 1, button: "left", clicks: 1 } },
  }, { nowSeconds: 1000 }).error, "invalid_message_payload");
});

test("rejects unknown key combinations and arbitrary action types", () => {
  const payload = {
    action_id: "cdefghijklmnopqrstuvwx",
    action: "key_combo",
    args: { combo: "ALT+F4" },
    reason: "Close a window",
    requires_local_approval: true,
  };
  assert.equal(validateDesktopBridgeEnvelope({
    ...base, kind: "action.request", payload,
  }, { nowSeconds: 1000 }).error, "invalid_message_payload");
});

test("validates encrypted frame metadata and caps image dimensions and payload size", () => {
  const frame = {
    ...base, kind: "screen.frame",
    payload: {
      frame_id: "cdefghijklmnopqrstuvwx",
      captured_at: 1000,
      mime_type: "image/jpeg",
      width: 1920,
      height: 1080,
      ciphertext: "x".repeat(32),
    },
  };
  assert.equal(validateDesktopBridgeEnvelope(frame, { nowSeconds: 1000 }).ok, true);
  assert.equal(validateDesktopBridgeEnvelope({
    ...frame, payload: { ...frame.payload, width: 5000 },
  }, { nowSeconds: 1000 }).error, "invalid_message_payload");
});

test("rejects unknown message kinds and extra payload keys", () => {
  assert.equal(validateDesktopBridgeEnvelope({
    ...base, kind: "shell.execute", payload: { command: "whoami" },
  }, { nowSeconds: 1000 }).error, "invalid_message_payload");
  assert.equal(validateDesktopBridgeEnvelope({
    ...base, payload: { reason: "user_requested", extra: "not allowed" },
  }, { nowSeconds: 1000 }).error, "invalid_message_payload");
});
