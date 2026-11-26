# ADR 0004: Paired Desktop Bridge for MEHR Live

- Status: Accepted for staged implementation
- Date: 2026-11-26
- Owners: MEHR AI STUDIO
- Related: ADR 0002 (Realtime transport), ADR 0003 (Direct Realtime WebRTC)

## Context

MEHR Live is intended to let a user talk to an AI agent while the agent can observe a user-approved view of a desktop application and assist with bounded UI actions. A phone may act as the voice/camera interface while a desktop companion connects to software such as AutoCAD. The desktop bridge is not implemented in the current branch.

A desktop-control feature has a higher security impact than ordinary chat. It can expose private screen content and cause real changes in desktop applications. The design must therefore make pairing, visibility, consent, action scope, and revocation explicit.

## Decision

Build the bridge as an optional, separately installed desktop companion. The companion establishes an outbound authenticated connection to a Worker Durable Object relay; it does not open an inbound listener on the user's LAN or expose a remote shell. The phone/browser and desktop companion join the same short-lived paired room.

The initial release is read-only screen assistance. Mouse and keyboard actions are a later opt-in capability, disabled by default and gated by local desktop approval.

### Pairing and session security

1. The desktop companion creates a one-time pairing challenge with a short expiry and displays it as a QR code plus a human-readable comparison phrase.
2. The phone/browser scans or enters the challenge after the user explicitly starts pairing.
3. Both endpoints establish an authenticated, short-lived device session. Use a reviewed, interoperable secure-channel implementation; do not invent a custom cryptographic protocol.
4. Pairing is bound to the verified user, tenant, desktop device, and browser device. A challenge is single-use and is invalidated after success, expiry, or cancellation.
5. Relay messages are authorized by the Worker and encrypted end-to-end between paired endpoints where the selected secure-channel library supports it.
6. Either endpoint can revoke the pairing. Desktop disconnect, application exit, token expiry, or a visible emergency-stop control ends the control session.

### Desktop companion

- Runs as a visible user-level process with a tray/status indicator; no hidden service or stealth persistence.
- Makes outbound TLS connections only. It does not expose a public or LAN listening port.
- Requests screen-capture permission through the operating system and displays a persistent capture indicator.
- Sends sampled, bounded screenshots or approved crops; no continuous full-resolution recording by default.
- Does not persist screenshots or transcripts by default. Any recording/export feature requires a separate explicit user action.
- Uses an OS-specific adapter behind a narrow interface so Windows can be validated first without coupling the protocol to one desktop OS.

### Action permission model

The first control-capable release may expose only these allowlisted primitives:
- Move pointer to a visible coordinate.
- Single click or double click on a visible target.
- Type user-approved text into the currently focused application.
- Send a small, explicit allowlist of non-privileged key combinations.

Every action request includes a session ID, monotonic sequence number, expiry, action type, arguments, and a short reason. The companion validates the schema and bounds locally before execution.

Default policy is deny. Each action requires a visible local approval prompt. A user may grant a narrowly scoped batch approval for a short interval, with the active scope shown continuously and a one-click stop control. The agent must not silently approve actions based on its own confidence.

Explicitly out of scope:
- Arbitrary shell or command execution.
- Running scripts, installing software, or changing OS security settings.
- Accessing passwords, password managers, authentication codes, or private key stores.
- Reading clipboard contents by default.
- File-system browsing, upload, deletion, or exfiltration.
- Administrator/root elevation.
- Hidden screen capture, hidden input, or control after pairing revocation.

### Relay and protocol

The Worker Durable Object acts as an authenticated message relay and room coordinator, not as a remote-desktop executor. It enforces:
- verified OIDC subject and tenant;
- one active desktop pairing per room unless explicitly extended;
- short pairing and session expiry;
- per-user and per-device rate limits;
- strict message-size and schema validation;
- monotonically increasing sequence numbers and replay rejection;
- heartbeat/lease expiry and cleanup on disconnect;
- audit metadata for approvals and actions, without storing screen pixels or typed content by default.

The desktop companion should prefer a peer-to-peer encrypted data channel when connectivity allows. The relay path remains available for signaling and fallback. Any fallback must preserve the same end-to-end authentication and authorization semantics.

### Suggested message envelope

```json
{
  "version": 1,
  "room_id": "opaque-room-id",
  "session_id": "opaque-session-id",
  "sequence": 42,
  "expires_at": 1795680000,
  "kind": "screen.frame | action.request | action.approval | action.result | session.stop",
  "payload": {}
}
```

This is an illustrative envelope, not an implemented API contract. The final schema must use a strict discriminated union per message kind and reject unknown fields.

## Alternatives considered

### Direct LAN WebSocket listener on the desktop
- Pros: low latency, no cloud relay for local use.
- Cons: inbound firewall rules, LAN exposure, certificate trust friction on phones, and difficult network isolation.
- Decision: rejected for the first release.

### Remote shell or unrestricted desktop automation
- Pros: broad capability and quick prototype.
- Cons: excessive privilege, high blast radius, poor user transparency, and difficult auditability.
- Decision: rejected.

### Cloud relay with server-visible commands and screen content
- Pros: simpler initial implementation and centralized diagnostics.
- Cons: server becomes a privacy-sensitive observation/control point.
- Decision: use only as a constrained fallback; prefer end-to-end encrypted payloads and avoid storing media.

## Consequences

Positive:
- The phone and desktop can cooperate without requiring an inbound desktop port.
- Pairing is explicit, revocable, and tied to authenticated identities.
- Read-only observation can ship before UI control.
- OS automation remains behind a replaceable adapter.
- User approval is enforced locally, even if the cloud account or relay is compromised.

Negative:
- Pairing, key lifecycle, reconnection, and relay reliability add engineering work.
- End-to-end encryption complicates server-side inspection and support diagnostics.
- OS-specific screen capture and input automation require separate implementation and testing.
- Local approval prompts reduce the degree of unattended automation by design.

## Acceptance gates

1. Threat model and protocol schema reviewed before implementation.
2. Pairing challenge is single-use, expires, and cannot be replayed.
3. Desktop companion makes outbound-only connections and displays an unmistakable active state.
4. Revocation and emergency stop terminate capture and control immediately.
5. Read-only screen assistance works without enabling input control.
6. Every control action is locally authorized, schema-validated, bounded, and auditable.
7. No arbitrary shell, hidden capture, privileged action, or file-system access is exposed.
8. Security tests cover expired tokens, wrong tenant/device, replayed sequence, oversized payloads, lock expiry, and disconnect races.
9. Android-to-desktop and desktop-to-desktop interoperability is tested before public release.

## Implementation sequence

1. Define the strict message schemas and threat model.
2. Implement pairing, relay lifecycle, heartbeat, and revocation with no screen or input permissions.
3. Add read-only screen capture with a visible indicator and bounded frame rate.
4. Test the phone-to-desktop live voice + screen workflow on a non-production environment.
5. Add one allowlisted UI action at a time, with local approval and emergency stop.
6. Add AutoCAD-specific workflows only after generic capture and input controls pass security and reliability tests.

## Current status

The branch now contains a standalone version-1 message-envelope validator and automated protocol tests (`cloudflare/desktop-bridge-protocol.mjs`, `tests/desktop-bridge-protocol.test.mjs`). It enforces exact envelope/payload keys, bounded expiry, monotonic sequence checks, bounded encrypted-frame metadata, a narrow action allowlist, and mandatory local approval on action requests. This is protocol groundwork only: no pairing endpoint, durable replay store, relay/WebSocket lifecycle, desktop companion, screen capture, or input adapter is implemented. No desktop action can currently be executed through this module.
