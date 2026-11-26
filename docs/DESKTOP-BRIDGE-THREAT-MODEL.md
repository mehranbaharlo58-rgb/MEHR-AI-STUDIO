# MEHR Desktop Bridge: Threat Model and Protocol Boundary

Status: implementation prerequisite; reviewed alongside ADR 0004.

## Assets

- User identity, tenant membership, and device-pairing authority.
- Desktop screen content and any data visible in approved application windows.
- Desktop input authority and unsaved work in connected applications.
- Pairing challenges, session keys, approval decisions, and sequence counters.
- Availability of the desktop companion and relay.

## Trust boundaries

1. The identity provider authenticates the user; the Worker validates signed access tokens and tenant claims.
2. The Worker/Durable Object relay coordinates pairing and forwards opaque messages. It is not trusted with plaintext screen frames or authority to execute desktop actions.
3. The desktop companion is the local policy enforcement point. It owns OS permission prompts, persistent capture indication, action validation, local approval, and emergency stop.
4. The phone/browser is an authenticated paired peer, not a trusted source of arbitrary commands.
5. The operating system and the locally installed companion are trusted to enforce capture and input permissions.

## Threats and required controls

| Threat | Required control |
|---|---|
| Pairing challenge guessed or intercepted | Cryptographically random, single-use challenge; short TTL; QR plus human comparison phrase; rate limit; bind claim to authenticated subject and tenant |
| Challenge replay or race | Atomic consume in Durable Object transaction; only one successful claimant; invalidate on cancel, expiry, or success |
| Cross-tenant/device access | Bind room to subject, tenant, browser device, and desktop device; authorize every join and message |
| Message replay/reordering | Persist per-sender sequence high-water mark; reject sequence less than or equal to last accepted; expire envelopes |
| Forged or oversized messages | Strict discriminated union, exact keys, payload size caps, rate limits, bounded strings/numbers |
| Relay reads screen content | End-to-end authenticated encryption; relay forwards ciphertext only; no frame persistence or body logging |
| Agent performs unintended action | Default deny; action allowlist; local approval prompt per action; visible short-lived scoped grants only if later explicitly designed |
| Hidden or persistent capture | User-level visible process; OS permission; persistent indicator; immediate stop on revocation/exit |
| Session survives disconnect | Heartbeat lease, bounded expiry, disconnect cleanup, explicit revocation and emergency stop |
| Compromised cloud account | Local desktop approval remains mandatory; relay cannot independently execute input |
| Secret leakage in logs | Never log access tokens, pairing secrets, ciphertext bodies, typed text, or screenshots; audit only minimal action metadata |

## Protocol constraints already encoded

The module cloudflare/desktop-bridge-protocol.mjs validates version 1 envelopes, exact field sets, opaque IDs, short expiry, strictly increasing sequence values when the caller supplies the persisted high-water mark, bounded encrypted-frame metadata, and a narrow action set. Every action.request must declare requires_local_approval=true.

The validator is not a substitute for persistence or authentication. The future relay must load and atomically update the sender's sequence high-water mark in Durable Object storage. A process-local counter is insufficient.

## Explicit non-goals

- Remote shell, script execution, arbitrary commands, admin elevation.
- Hidden screen capture or unattended desktop input.
- Clipboard, password manager, authentication-code, or private-key access.
- File-system browsing, transfer, deletion, or exfiltration.
- Server-side storage or inspection of screen pixels and typed content.

## Release gates

- Pairing race/replay tests pass against Durable Object transactions.
- Wrong subject, tenant, device, token expiry, and revoked-session tests pass.
- Oversize, malformed, unknown-field, sequence replay, and expiry tests pass.
- Relay cannot decrypt or persist screen content.
- Desktop capture indicator and emergency stop are verified on the target OS.
- No input action is enabled until local approval and allowlist tests pass.
- Phone-to-desktop workflow passes on a non-production deployment.