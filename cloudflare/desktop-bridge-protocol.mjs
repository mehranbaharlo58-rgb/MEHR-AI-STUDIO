const ENVELOPE_KEYS = ["version", "room_id", "session_id", "sequence", "expires_at", "kind", "payload"];
const ID_PATTERN = /^[A-Za-z0-9_-]{22,64}$/;
const ACTION_KEYS = new Set(["move_pointer", "click", "type_text", "key_combo"]);
const KEY_COMBOS = new Set(["CTRL+S", "CTRL+Z", "CTRL+Y", "CTRL+C", "CTRL+V", "ESC", "ENTER", "TAB", "SHIFT+TAB"]);

function exactKeys(value, keys) {
  return value && typeof value === "object" && !Array.isArray(value) &&
    Object.keys(value).length === keys.length && Object.keys(value).every((key) => keys.includes(key));
}

function boundedString(value, min, max) {
  return typeof value === "string" && value.length >= min && value.length <= max;
}

function validAction(payload) {
  if (!exactKeys(payload, ["action_id", "action", "args", "reason", "requires_local_approval"]) ||
      !ID_PATTERN.test(payload.action_id) || !boundedString(payload.reason, 1, 240) ||
      payload.requires_local_approval !== true || !payload.args || typeof payload.args !== "object" ||
      Array.isArray(payload.args)) return false;

  if (payload.action === "move_pointer") {
    return exactKeys(payload.args, ["x", "y"]) &&
      Number.isInteger(payload.args.x) && payload.args.x >= 0 && payload.args.x <= 8192 &&
      Number.isInteger(payload.args.y) && payload.args.y >= 0 && payload.args.y <= 8192;
  }
  if (payload.action === "click") {
    return exactKeys(payload.args, ["x", "y", "button", "clicks"]) &&
      Number.isInteger(payload.args.x) && payload.args.x >= 0 && payload.args.x <= 8192 &&
      Number.isInteger(payload.args.y) && payload.args.y >= 0 && payload.args.y <= 8192 &&
      ["left", "right"].includes(payload.args.button) &&
      [1, 2].includes(payload.args.clicks);
  }
  if (payload.action === "type_text") {
    return exactKeys(payload.args, ["text"]) && boundedString(payload.args.text, 1, 1000);
  }
  if (payload.action === "key_combo") {
    return exactKeys(payload.args, ["combo"]) && KEY_COMBOS.has(payload.args.combo);
  }
  return ACTION_KEYS.has(payload.action) ? false : false;
}

function validPayload(kind, payload) {
  if (kind === "screen.frame") {
    return exactKeys(payload, ["frame_id", "captured_at", "mime_type", "width", "height", "ciphertext"]) &&
      ID_PATTERN.test(payload.frame_id) && Number.isSafeInteger(payload.captured_at) &&
      ["image/jpeg", "image/webp"].includes(payload.mime_type) &&
      Number.isInteger(payload.width) && payload.width > 0 && payload.width <= 3840 &&
      Number.isInteger(payload.height) && payload.height > 0 && payload.height <= 2160 &&
      boundedString(payload.ciphertext, 16, 350000);
  }
  if (kind === "action.request") return validAction(payload);
  if (kind === "action.approval") {
    return exactKeys(payload, ["action_id", "approval_id", "approved"]) &&
      ID_PATTERN.test(payload.action_id) && ID_PATTERN.test(payload.approval_id) &&
      typeof payload.approved === "boolean";
  }
  if (kind === "action.result") {
    return exactKeys(payload, ["action_id", "status", "error_code"]) &&
      ID_PATTERN.test(payload.action_id) && ["executed", "denied", "failed"].includes(payload.status) &&
      (payload.error_code === null || (typeof payload.error_code === "string" && /^[a-z0-9_]{1,64}$/.test(payload.error_code)));
  }
  if (kind === "session.stop") {
    return exactKeys(payload, ["reason"]) &&
      ["user_requested", "desktop_exit", "token_expired", "revoked", "emergency_stop", "heartbeat_timeout"].includes(payload.reason);
  }
  return false;
}

/**
 * Validate a version-1 desktop bridge message before relay.
 * Encrypted frame content remains opaque; the relay must never persist it.
 * lastSequence is the last accepted sequence for this sender/session.
 */
export function validateDesktopBridgeEnvelope(envelope, {
  nowSeconds = Math.floor(Date.now() / 1000),
  lastSequence = 0,
  maxLifetimeSeconds = 60,
} = {}) {
  if (!exactKeys(envelope, ENVELOPE_KEYS)) return { ok: false, error: "invalid_envelope_shape" };
  if (envelope.version !== 1 || !ID_PATTERN.test(envelope.room_id) ||
      !ID_PATTERN.test(envelope.session_id)) return { ok: false, error: "invalid_identity" };
  if (!Number.isSafeInteger(envelope.sequence) || envelope.sequence <= lastSequence || envelope.sequence < 1) {
    return { ok: false, error: "replayed_or_invalid_sequence" };
  }
  if (!Number.isSafeInteger(envelope.expires_at) || envelope.expires_at <= nowSeconds ||
      envelope.expires_at > nowSeconds + maxLifetimeSeconds) return { ok: false, error: "invalid_expiry" };
  if (!["screen.frame", "action.request", "action.approval", "action.result", "session.stop"].includes(envelope.kind) ||
      !validPayload(envelope.kind, envelope.payload)) return { ok: false, error: "invalid_message_payload" };
  return { ok: true, envelope };
}
