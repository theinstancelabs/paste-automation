# Stationary camera LED restore

`Restore_Paste_Camera_LED.js` is staged with `PASTE_CAMERA_LED_RESTORE_ENABLED = false`. Parent dispatch follows independent source review and a newly verified enabled/homed state. A reconnect or recovery-finalizer result alone does not establish that state.

Create `automation/plans/paste-camera-led-request.json` from a fresh native snapshot with schema1, scope `stationary-native-camera-LED-restore`, fresh UUID, `createdMs`, exact `jvmStartMs`, operator, `reviewedStationaryLED: true`, live configuration SHA-256, all five `expectedRaw`/`expectedDriver` coordinates, and all four `expectedNativePoses`. It expires after five minutes; its claimed UUID cannot be retried. The request and starting snapshot are frozen in the runtime.

The existing native worker checks idle/stopped, enabled/homed, connected non-simulation driver, original reader and commands, error latch, empty motion/subordinate queues, no parts, quarantined N2, and pinned installed JAR. It performs full XYZAB M114 before and after exactly one `d.actuate(led,true)` call. The pinned boolean template expands to `M150 P255 R255 U255 B255`, and the full response queue must contain exactly one clean LED ACK. This bypasses ReferenceActuator coordination, which can invoke generic completion and wrap the paste B axis. No move, home, vacuum or motor-current command is issued.

Before/after top and bottom images use already-open raw capture streams without lighting wrappers. Reports retain all response lines and snapshots under `automation/evidence/paste-camera-led-UUID`. Failed attempted I/O retains busy state, stops the worker and cancels queued work; no cleanup command or automatic replay is attempted. Acknowledged light output is separate from visual image acceptance, and no physical calibration is established.

Offline checks: four request/command contract tests pass; installed Nashorn compiles the adapter without evaluating it. Installed boolean-actuate bytecode sends the expanded command through `sendGcode`, with no planner coordination. No hardware dispatch was used during implementation.
