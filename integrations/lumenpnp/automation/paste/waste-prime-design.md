# Staged waste-only priming contract

This is a design and test specification, not an enabled adapter or a dispensing recipe. `Observe_Paste_B.js` remains disabled, with its existing minus-one-degree contract unchanged. No motion route or measured profile is supplied here.

## Proposed operation

One explicitly reviewed request commands exactly **minus 20 raw B degrees**, as an absolute native target `savedB - 20`. Raw X/Y/Z/A remain fixed. Use the existing OpenPnP driver and single worker, a partial B-only native planner target, the audited error latch, and complete before/after M114 responses. Do not invoke a nozzle rotation helper, wrap B, issue G92, reverse, retry, or automatically release pressure.

The receiver is an identified, restrained waste target. A measured right-tip height and receiving-surface height must establish a noncontact gap whose **lower uncertainty bound is at least 1 mm**, at the exact current XYZ/A pose. The profile also includes an explicitly reviewed upper gap bound, both-head clearance, installed needle identity, and hashed measurement evidence. A current image confirms the target and local clearance; it does not replace a height measurement. A new home, changed tip, moved receiver, changed configuration, or changed pose invalidates the applicable profile evidence.

Each successful increment ends in a stationary observation boundary. Review a new image of the needle outlet and receiver and record one of: no visible paste; emerging paste but not yet consistent; consistent paste at the tip; or abnormal behavior. An observation must bind the previous request/report and images. Only a reviewed continuation after the first two results can authorize another increment. Consistent output ends priming; abnormal behavior stops it. No visible output does not authorize an automatic loop or establish an empty syringe. Neither an ACK nor a droplet proves calibrated delivered volume.

## Displacement and rate

Using the conditional nominal model (19:32 gearing, 0.5 mm screw pitch, 9.5 mm syringe bore), 20 motor degrees represent 0.0164931 mm piston travel and 1.169064 microlitres ideal displacement. A 300-degree ceiling represents 0.247396 mm and 17.535957 microlitres. Compliance, trapped air, backlash, delayed flow and obstruction prevent treating these values as delivered volume or a pressure limit.

At a verified setting of 4.44 controller steps per B unit, absolute B720 to B700 corresponds to approximately count3197 to count3108: 89 steps. Later 20-degree increments can differ by one step because absolute targets are quantized. Validate absolute start and target counts with the actual firmware rounding rule; do not repeatedly subtract a rounded 88.8-step delta.

The proposed commissioning configuration remains limitRotation=false, wrapAroundRotation=false, invertLinearRotational=true, feed limit100, acceleration500 and jerk2000, with native speed fraction0.05. The product100×0.05 is a **5-unit/s ceiling**, not a measured or guaranteed native trajectory rate. Twenty degrees would take four seconds at a constant5 degrees/s, plus acceleration effects; installed native planning can choose a lower rate. Before activation, capture the actual native command projection and exact expanded M204/G1 lines through a disconnected/intercepted formatter. Require one literal B-only target, positive bounded rates, no XYZA words, and no hidden wrap or offsets. Never transmit the preview.

## Session accounting

Use one hash-bound session ledger with an explicit total ceiling no greater than300 degrees. Reserve the entire20 degrees and verify the saved bytes **before** any controller query or motion. Store per-entry startB, targetB, reservedDegrees, request identity, profile/configuration/session identity, and observation link. Sum entry reservations; entry count is no longer a degree count. Derive cumulative absolute target from the original B and sum, never from a guessed delivered dose.

Pending, failed or uncertain entries retain their reservation and block continuation. A terminal verified entry requires full M114 and controller-count evidence, unchanged XYZA, saved after-images, and a verified ledger write. No ledger reset, profile substitution, new request UUID, process restart or reconnect may silently refund consumed/reserved displacement. If a prior minus-one-degree direction test belongs to this session, charge it too: one plus fourteen20-degree increments is281 degrees; a further20 would exceed300. There is no requirement to repeat ten barely observable one-degree tests before a separately reviewed priming increment.

## Required offline checks before any activation

- Exact minus20 accepted; zero, positive, minus1, minus19.9, minus21, NaN and alternative command/axis parameters rejected by the new priming scope.
- Literal B720→700 and later absolute targets preserve XYZA, never normalize into a rotation interval, and produce the exact expected controller counts under the audited firmware rule.
- Fifteen20-degree reservations reach300; the sixteenth fails. Prior charged displacement is included. Ledger corruption, duplicate UUID, profile/config/JVM drift, pending/faulted entry and changed previous hash all fail before another command.
- Missing receiver, uncertain gap extending below1 mm, stale image, moved pose, mismatched needle, missing measurement provenance and unclear both-head envelope reject the request.
- No second increment without a fresh review of the previous terminal report and images. A consistent droplet, abnormal result, or ambiguous observation cannot authorize another increment.
- Native formatter traces prove the exact expanded command/rate and B-only movement. Full-response traces cover error, reset, resend, disconnect, timeout, malformed/duplicate position, missing following ACK, unexpected count changes and delayed responses.
- Fault traces contain no subsequent movement, reverse, automatic pressure release, retry or ledger refund. Successful traces end at an observation boundary with no queued continuation.

These checks extend the current policy, which still permits only minus1 and a1–10-degree ledger. Merely widening its request value would leave incorrect reservation arithmetic and incomplete validation.
