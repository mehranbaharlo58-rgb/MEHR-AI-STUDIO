# MEHR Universal Context & Desktop Control

## Product decision

MEHR is a multimodal collaboration agent that can understand the user's permitted visual/audio context and, when explicitly enabled, collaborate with the user inside connected digital environments. AutoCAD is one example, not the product boundary.

The target experience combines:
- Phone-based live voice and camera interaction.
- Desktop screen observation and application context.
- Shared human/agent mouse and keyboard control.
- Context continuity across the phone, desktop, and supported real-world visual inputs.
- Specialist-agent orchestration, verification, and teaching.
- A visible, immediate user override and stop control.

This document defines the product and engineering baseline. It does not claim that the bridge or computer-control runtime is already implemented.

## Core architecture

```text
MEHR Mobile App / Mobile Web
  - live voice + optional camera
  - user intent, consent, session controls
  - session status, action approvals, handoff
          |
          | authenticated pairing + encrypted session
          | USB network / local Wi-Fi / LAN / relay
          v
MEHR Desktop Bridge (signed, user-installed process)
  - device pairing and session authentication
  - screen capture adapter
  - accessibility/context adapter
  - mouse + keyboard action adapter
  - human-input arbitration
  - local policy enforcement and audit events
          |
          | normalized observations + bounded action requests
          v
MEHR Context Gateway
  - multimodal event normalization
  - session/context state
  - provider adapters
  - tenant, quota, consent and policy enforcement
          |
          v
MEHR Agent Orchestrator
  - supervisor / task planner
  - vision and screen-understanding agent
  - application/domain specialist agents
  - action planner
  - independent verification agent
          |
          v
MEHR Live response: voice / text / visual pointer / avatar
```

The Desktop Bridge is the only component allowed to translate approved MEHR actions into local operating-system input. The model/provider never receives raw operating-system privileges or desktop credentials.

## Device connectivity

The connection method is a transport choice, not a different control implementation.

1. **Local Wi-Fi / LAN:** preferred first implementation. Phone and computer pair on the same trusted network.
2. **USB:** supported through a network-over-USB/tethered link where the operating systems expose it. The bridge protocol remains identical. Do not depend on USB keyboard emulation as the primary architecture.
3. **Remote relay:** optional later path using an authenticated outbound connection. No unauthenticated inbound desktop port.
4. **Future devices:** tablets, smart displays, wearables and other endpoints implement the same capability contract where platform APIs permit.

Every pairing requires a visible confirmation on the desktop and the phone. Pairing credentials are short-lived, revocable, scoped to a device and stored using platform secure storage. Local discovery must not silently authorize a new device.

## Observation contract

A desktop observation is a timestamped, session-scoped event containing only the fields enabled by the user:
- display/frame metadata and image payload or an approved cropped region;
- active application/window metadata when available;
- display dimensions, scaling and coordinate-space metadata;
- optional accessibility tree or semantic element descriptions;
- capture timestamp, sequence number and freshness indicator;
- consent scope and capture mode.

Observation modes:
- **Screen snapshot:** explicit one-time capture.
- **Screen stream:** user-enabled continuous or sampled capture with visible indicator and configurable sampling limits.
- **Semantic context:** app/window/control metadata through OS accessibility APIs, where supported.
- **Phone camera:** separate opt-in input; never imply that a desktop screenshot is a camera stream or vice versa.

Prefer semantic/accessibility targets over raw screen coordinates when reliable. Use visual coordinates as a fallback and always map model coordinates to the original display coordinate space.

## Action contract

The bridge exposes a narrow, typed action vocabulary:
- move pointer;
- click / double-click / context-click;
- scroll;
- key press / key chord;
- type text;
- drag;
- request fresh screenshot;
- yield control / cancel session.

Every action request must include:
- session ID and unique action ID;
- target display and coordinate-space version when applicable;
- action type and bounded parameters;
- reason/intent summary;
- risk classification and approval requirement;
- expiry/deadline and idempotency policy.

The bridge validates every field locally. It rejects unknown actions, stale sessions, expired requests, out-of-bounds coordinates, disallowed key combinations, excessive action batches and requests outside the granted scope.

Do not expose arbitrary shell execution, unrestricted scripting, credential stores, or general filesystem access through the initial Desktop Bridge.

## Shared-control model

The product must support explicit modes:

1. **Observe:** the agent can see permitted context but cannot control input.
2. **Guide:** the agent explains and may show a visual pointer/annotation; the user performs actions.
3. **Co-pilot:** the agent can perform individually approved low-risk actions; user input always takes priority.
4. **Delegated task:** the user authorizes a bounded sequence with stated goal, allowed applications/actions, time/step budget and stop conditions.

Human input arbitration:
- physical user input preempts agent input immediately;
- an emergency stop revokes the active action lease;
- only one actor owns pointer/keyboard injection at a time;
- agent actions run in short batches followed by a fresh observation;
- the user can pause, resume, take control, or end the session at any time;
- reconnect never silently resumes control.

## Safety, privacy and trust boundaries

- The user explicitly starts screen/camera/audio capture and sees persistent indicators.
- Capture can be paused or stopped independently for screen, camera and microphone.
- No background capture when the session is inactive.
- Raw screen/audio/video data is not persisted by default.
- Sensitive fields and secrets must be redacted where feasible; the agent must not request passwords or one-time codes.
- Screen contents, documents, websites and other third-party text are untrusted data. They cannot grant permissions or override user intent.
- Financial, destructive, externally visible, security-setting, account, permission, file deletion/overwrite, or data-sharing actions require explicit just-in-time confirmation.
- User confirmation is bound to the exact action or bounded action batch; it is not blanket authorization for future actions.
- The bridge must fail closed on authentication, policy, freshness or connectivity errors.
- Per-session limits cover action count, duration, capture rate, data volume and provider spend.
- Every action produces an auditable result: accepted, rejected, executed, interrupted or failed.
- The product must provide a visible emergency stop and local uninstall/revocation path.

## Platform adapter strategy

The bridge core is platform-neutral. OS-specific adapters are isolated behind interfaces.

- **Windows first:** screen capture API; UI Automation for semantic context; approved input injection for mouse/keyboard; explicit OS permission and signed installer.
- **macOS:** Screen Recording and Accessibility permissions; platform accessibility APIs; input control only after user-granted permissions.
- **Linux:** desktop/session-specific capture and accessibility/input adapters. Wayland restrictions and portal permissions must be respected; do not assume X11 behavior.
- **Mobile:** phone is initially the controller and live sensor endpoint, not a privileged remote-control implant on the desktop.

Capability discovery reports what the current OS/session actually supports. The UI must not advertise unavailable controls.

## Internal service interfaces

Initial conceptual interfaces (names may be adjusted to match repository conventions):

- `PairingService`: create, approve, revoke and rotate device pairing.
- `DesktopSessionService`: start, pause, resume, stop and expire sessions.
- `ObservationProvider`: capture screen, metadata and semantic context.
- `InputController`: execute one validated action or a bounded batch.
- `ControlArbiter`: acquire/release input lease and prioritize human input.
- `PolicyEngine`: classify action risk and require approval.
- `AuditRecorder`: append immutable session/action outcomes.
- `ContextGateway`: correlate desktop observations with voice, camera and agent events.

All interfaces return structured results and explicit capability/permission states. Provider-specific APIs stay behind adapters.

## Verification loop

The fundamental computer-use cycle is:

1. Receive the user's goal and current consent scope.
2. Obtain a fresh desktop observation.
3. Resolve the target using semantic context where possible; otherwise use image coordinates.
4. Produce a short action plan with risk labels.
5. Request approval when policy requires it.
6. Execute a bounded action batch through the local bridge.
7. Capture a new observation.
8. Verify the intended state change independently.
9. Continue, recover, yield to the user, or stop.

A model saying an action succeeded is not evidence. Success requires an observed postcondition or an explicit failure state from the bridge.

## Delivery plan and acceptance gates

### D0 — Architecture baseline
- Product boundary, threat model, transport model, observation/action contracts and staged plan documented.
- No claim of working remote control.

### D1 — Desktop Bridge local prototype
- Windows-only signed-in desktop process.
- Local pairing with visible approval.
- Snapshot capture and safe Observe mode.
- Automated tests for session expiry, revocation, permission denial and capture shutdown.

### D2 — Phone-to-desktop connectivity
- Phone and desktop pair over local Wi-Fi.
- USB network transport tested where supported without changing the protocol.
- Authenticated encrypted session, reconnect and explicit teardown.
- Android Chrome/mobile client interoperability verified.

### D3 — Guided and co-pilot control
- Guide mode with visual pointer/annotation.
- Narrow mouse/keyboard actions, local validation and emergency stop.
- User input preempts agent input.
- Screenshot/action/screenshot loop and verified postconditions.

### D4 — Context-aware collaboration
- Voice session correlated with desktop context.
- Specialist agents and task memory.
- Risk-based approval and independent verification.
- Cross-application tests on a small supported-app matrix.

### D5 — Cross-platform expansion
- macOS and Linux adapters.
- Broader device and display support.
- Optional remote relay and wearable integration after security review.

### Required release tests
- Unpaired or revoked phone cannot observe or control the desktop.
- Expired/replayed action IDs are rejected.
- Physical user input preempts agent control.
- Emergency stop halts pending and active actions.
- Disconnect, sleep, lock and app crash fail closed.
- Out-of-bounds and stale-coordinate actions are rejected.
- Sensitive/destructive actions pause for explicit approval.
- Capture indicators and shutdown work in all exit paths.
- No secrets appear in client bundles, logs or telemetry.
- Verification distinguishes actual postcondition from model assertion.

## Relationship to MEHR Live

MEHR Live owns human-facing real-time voice, camera and avatar interaction. Universal Context Gateway normalizes all permitted observations. Desktop Bridge owns local screen capture and input execution. MEHR Orchestrator plans and delegates tasks. These are separate bounded components connected by authenticated, typed events.

The existing MEHR Live L0 shell is a prerequisite UI foundation only. It does not implement the Desktop Bridge, live provider calls, screen capture transport, or computer control.

## Product claims

Until end-to-end acceptance tests pass, describe these capabilities as planned or in development. Do not claim universal OS support, continuous environmental understanding, remote control, or autonomous task completion based on architecture documents alone.
