# MEHR Windows Desktop Bridge — Engineering Note

## Scope of this increment

This increment adds:
- a platform-neutral `DesktopAdapter` protocol and `DesktopBridgeRuntime`;
- fail-closed consent and foreground-application allowlisting;
- typed actions, coordinate bounds, one-time action IDs, explicit approval and human-control arbitration;
- an optional Windows adapter for monitor capture and typed mouse/keyboard operations;
- unit tests using a fake adapter and platform guards.

It does **not** yet provide phone pairing, a network listener, USB transport, Wi-Fi streaming, WebRTC, remote authentication, a Windows background service, or physical-input event hooks. It is not yet a usable phone-to-PC product.

## Install the optional Windows dependencies

On a Windows 10/11 development machine with Python 3.11+:

```powershell
py -m pip install -e ".[dev,desktop-windows]"
```

The optional adapter uses:
- PyAutoGUI for bounded mouse/keyboard events;
- MSS for in-memory monitor capture;
- Pillow to encode screenshots in memory;
- pywin32 and psutil to identify the foreground process.

No process launching, shell execution, file modification, or unattended startup is implemented.

## Integration contract

A caller creates a `DesktopSessionPolicy` with:
- explicit consent;
- an allowlist of foreground process IDs (executable stems, e.g. `acad`);
- a mode and separately enabled pointer/keyboard scopes.

It then constructs `DesktopBridgeRuntime(policy=..., adapter=WindowsDesktopAdapter())`.

The runtime is deliberately not exposed over a network. A future pairing service must authenticate the phone, bind a short-lived session to one desktop, and pass every request through this runtime. Never expose the adapter directly to a network client.

## Current behavior and limitations

- Screen capture is one monitor at a time and returns in-memory PNG bytes.
- The capture can include other visible windows and notifications on that monitor. Do not enable it around confidential content unless the user has explicitly approved that screen context.
- Monitor-relative coordinates are translated to virtual-desktop coordinates, including monitors positioned left of the primary display.
- Non-ASCII text is rejected by the first Windows adapter. Persian and other Unicode input require a later clipboard adapter with safe clipboard restoration.
- Foreground application identity is process-level, not window/tab-level.
- Physical keyboard/mouse event hooks are not implemented yet. The arbitration API exists, but real hardware-event preemption is not yet wired to Windows.
- The current adapter does not verify that the requested UI action achieved the intended task result. A later observation and verification layer must do that.
- USB and Wi-Fi are transport choices for a future authenticated pairing layer; neither is implemented in this increment.

## Required next acceptance gates

1. Windows 10/11 smoke test on a disposable test account and non-sensitive desktop.
2. Confirm screenshot dimensions and image decoding for primary and secondary monitors.
3. Verify pointer coordinates on primary and offset secondary monitors.
4. Verify PyAutoGUI fail-safe and immediate stop behavior.
5. Add a Windows physical-input hook that ignores injected events and reliably preempts agent input.
6. Add a pairing protocol with short-lived credentials, replay protection, explicit user confirmation, and TLS or an equivalent authenticated encrypted channel.
7. Add Android pairing and end-to-end tests before claiming phone-to-desktop control.
