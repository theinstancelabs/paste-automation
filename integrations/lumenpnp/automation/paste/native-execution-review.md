# Native paste execution review — 2026-09-30

`Run_Paste_Air.js` remains disabled. Its `PASTE_PHYSICAL_EXECUTION_ENABLED = false` gate is necessary even after a measured profile becomes available. Successful bounded camera surveys and stationary vacuum recording do not validate this older runner, a Z probe, or a wet paste run.

## Concrete blockers in the staged air runner

The runner uses `UiUtils.submitUiMachineTask`, `N2.moveTo`, and `N2.waitForCompletion`. The installed OpenPnP `AbstractMachine.submit` wrapper performs global planner completion on success and exception cleanup. The installed NullMotionPlanner completion path can wrap mapped rotation coordinates and issue global offsets. N2 includes physical B; the observed B coordinate of 720 must not be normalized as a side effect of an air move. The newer camera survey deliberately uses a partial controller-axis target, a camera mapping only X/Y, `SpeedOverPrecision`, and the existing executor without that wrapper. The air runner does none of this.

`right.waitForCompletion` occurs before its live configuration hash check. Its exception path rethrows into the public wrapper despite recording `fault-no-recovery-motion`; that record does not prevent wrapper cleanup. Its current `checkRaw` covers axes mapped through N2, not an immutable full-machine X/Y/Z/A/B snapshot, and native backlash or interlocks can add behavior after the transform check. Its 0.001 comparison tolerance also predates the observed native driver-report rounding. These are replacement requirements, not permission to relax tolerances and enable the flag.

## Controller-owned air adapter required before activation

Build a separately reviewed adapter using the established single-owner executor and exact installed driver/planner identity. Preserve the reviewed task ownership, empty queue/pending checks, one-shot request, immutable numeric snapshot before M114, and explicit failure latch. No public task wrapper, generic safe-Z call, N2 completion call, serial reopening, or raw fork-G-code replay.

Bind each request to the current JVM, exact live configuration digest, measured registration/profile, fresh clearance images and starting raw/native poses. Preflight the entire path in the calibrated needle frame, then transform into controller coordinates and prove unchanged raw Z/A/B. Verify the swept path of both heads and mounted syringe, not only the point endpoints. Bounds alone do not prove obstacle clearance. Use only a mapped object that excludes physical rotation for completion, and independently verify before/after firmware coordinates, retaining the distinction between native completion and physical evidence. Any pause/cancel for an air path holds at an already verified joint clearance; no implicit recovery lift is established.

## N1 surface probe requirements

Use the reviewed ES5 `vacuum-probe-policy.cjs` with a fresh measured baseline and explicit response direction/noise thresholds. The separate baseline recorder measures free-air behavior; it does not establish a contact threshold. Partial response, opposite-sign response, lost response, elapsed deadline or incorrect step acknowledgement must prevent further descent.

The native coupling is `z2 = 63 - z1`: decreasing raw Z/N1 height raises N2, while retracting N1 lowers N2. This is an axis mapping, not a measured collision envelope. A bounded N1 descent requires a restrained, flat, identified target beneath N1, a verified maximum descent/minimum raw Z, clearance above the rising N2 syringe assembly, and a safe observed return pose. A free scrap can seal and lift before the nozzle makes repeatable contact. A seal candidate is not proof of surface height.

Each increment must be an explicit partial raw-Z target with X/Y/A/B invariant, measured start and target bounds, and direct-driver stillstand semantics independently reviewed to avoid a null-head or N2 planner wrap. Sensor sampling begins only after acknowledged stillstand. On a normally confirmed seal candidate, release VAC1 and confirm the normal OFF command sequence before returning to the previously observed start Z. Uncertain transport or motion must latch without blind OFF/retract commands. Do not use a generic safe-Z return or historical feeder pickup thresholds/coordinates. See `vacuum-native-review.md` for installed API evidence and exact-template transport constraints.

## Wet run requirements

Wet operation additionally needs measured right needle XY offset and tip/surface gap, needle/hub geometry, verified right-head travel and shared-Z envelope, a registered restrained coupon, and calibrated dispense/retraction behavior for the installed paste, syringe and needle. Nominal gear ratio and bore determine ideal plunger displacement only; they do not establish deposited volume or pressure relaxation.

Review a dedicated native partial-B movement and its completion path before any dosing. Confirm absolute/relative interpretation, steps/degree, usable stroke, motion rate and acceleration, bounds against cartridge damage, and invariance of X/Y/Z/A. The existing B=720 must be preserved as the starting coordinate; no automatic G92/wrapping or legacy N24 rotation correction is acceptable. Do not adapt the XY camera survey by merely adding B to its allowed axes.

Shared-Z motion makes an automatic “clearance lift” asymmetric: raising the paste tip lowers N1. A wet pause/cancel lift requires a verified coupled path and both-head end clearance; until then pause/cancel behavior is uncommissioned. Software stop/ACK is not a physical emergency stop, paste shutoff or observed collision-free result.

## Review provenance and limits

Reviewed canonical `Run_Paste_Air.js`, `safety.cjs`, the current survey and vacuum recorder, and installed OpenPnP bytecode. Audited installed JAR SHA256: `bcd34923ae91d61a96b98b4c82c93cdc90093ff94292270fd0a18fc6f96f7752`. No gate was enabled and no machine operation was performed for this review. The fork's offline tests and local policy tests establish software behavior only. Actual FTP pad geometry is board-design evidence, not current board registration or dispensing calibration.
