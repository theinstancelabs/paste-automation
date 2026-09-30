# Native OpenPnP paste integration (staged)

The pure planner from `/home/lumen/paste-automation` at `c497bfbef2f7347538966c129bf7ac7bdc2c1a0f` is integrated for offline validation and review. The fork's serial/browser runner is **not** integrated. OpenPnP remains the sole controller owner, using the existing local reviewed Java Attach dispatcher; no serial socket, serial library or second controller is introduced.

**General paste air-path execution is disabled in code.** Bounded camera survey and stationary vacuum baseline have separate reviewed routes; they are not dispensing or surface probing. `Run_Paste_Air.js` contains `PASTE_PHYSICAL_EXECUTION_ENABLED = false`. The current unmeasured profile and false session attestations also fail closed. The staged native runner has been independently inspected and compiled with the installed Nashorn engine, but has never been executed on this machine. Passing offline tests does not validate its physical behavior. Do not remove the code gate: the [replacement native adapter](native-air.md) still requires measured path/session evidence, activation review, and a verified native error/reset latch. The currently absent error regex is an explicit activation blocker; software has not changed that setting. Measurements alone do not make this implementation ready. In-memory quarantine or installed event files alone are not proof that every manual UI path is guarded.

`installation-lock.json` also suspends all legacy reviewed actions in both the Python entrypoint and OpenPnP dispatcher. A missing, malformed, or locked file remains blocked. The explicit exemptions are `paste-state`, `paste-quarantine`, `paste-error-latch`, `paste-position-barrier`, `paste-connect-inspect`, `paste-measure`, `paste-survey`, `paste-survey-audit`, `paste-survey-release`, `paste-vacuum-baseline` and code-disabled `paste-air`. Each has separate guards; exemptions do not permit arbitrary legacy actions. Audit/release routes are bound to one diagnosed historical survey fault. The bounded pickup, camera verification, registration and backup script sources remain intact; deliberately release this lock only after the installation and both-head clearance review. This lock does not intercept direct manual OpenPnP UI actions, which require the separate N2 quarantine and supervised operating restrictions.

See [commissioning procedure](../operations/paste-commissioning.md) and preserve the current [setup/restart workflow](../operations/setup-and-restart.md). Never copy historical N1 calibration into the extruder profile. Known N1/N2 IDs in the pending profile are identification, not calibration. Firmware/settings are recorded by the separate `paste-state` action; no firmware flash is assumed or performed.

## Offline preparation

Copy `right-head-profile.pending.json` to a private measurement record and complete **all** fields from current evidence. `calibrated: true` attests actual measurements, not completion of a calibration routine. Then:

```sh
node automation/paste/prepare-air-plan.mjs measured-job.json measured-profile.json reviewed-air-plan.json
node --test automation/paste/safety.test.cjs
```

The CLI checks the fork's exact Git commit and pure planner bytes, invokes that planner with `dryRun: true`, emits its preview alongside native points, and refuses to overwrite output. It rejects wet mode and board-coordinate shortcuts. The stored G-code is review-only and is never sent to the controller.

`job.coordinateFrame: "machine"` here means points captured/transformed into the **current OpenPnP N2 tip-location frame in millimeters**, not controller XYZ or raw Gerber XY. Do not apply fork camera offsets again. Transfer registration explicitly with independent distant/asymmetric camera checks. `safeZ` and `leftClearanceZ` describe one measured joint clearance pose; both head envelopes and the entire connecting XY segments, including backlash motion, syringe/cables, clamps and feeders, must be clear. Bounding endpoints alone does not establish this.

`rawBounds` maps actual controller-axis IDs to measured `{ "min": ..., "max": ... }` intervals for raw X/Y. Both native and raw bounds are required. `liveConfigurationSha256` is the SHA-256 of the UTF-8 output of `Configuration.createSerializer().write(machine, StringWriter)` **after** the dedicated extruder quarantine/configuration is established. It detects altered driver commands, axis mapping/transform parameters, offsets and other saved-in-memory machine settings. It is not the disk `machine.xml` hash. Capture and retain the exact serialized snapshot when measuring; do not guess its hash. The runtime verifies the live serialization before motion.

The fork preview uses `travelFeed/zFeed/dispenseFeed` in mm/min or rotational degrees/min. The native runner uses `speedFraction`, a separately measured OpenPnP motion-speed fraction, limited to 0.1 for first commissioning. These are different speed controls. Do not infer native feed rate from the preview G-code. Retain a `nativeSpeedRecord` verifying actual configured driver limits and conservative commissioning speed.

## Replacement staged native air behavior

The replacement preserves offline plan schema 1 and adds `nativeExecution` to the supervised session. It binds exact raw/driver/all-camera-and-head poses, fresh clearance evidence, selected X/Y axis order, segment size, and a SHA-256 of the complete transformed native path. All measurement fields remain pending. See [native air contract and activation limits](native-air.md).

The measured N2 tip-frame points are transformed before any move, then split into one-axis raw X/Y steps at constant joint clearance. Both complete-path swept clearance and native/raw bounds are required. The native speed fraction must be between the installed minimum 0.05 and the commissioning maximum 0.1, avoiding silent speed clamping. The top camera's X/Y-only mapping provides completion without N2 rotary wrapping. There is no public machine-task wrapper, generic lift/park, N2 move/completion, serial reopening, actuation, or raw fork-G-code execution.

Cooperative `paste-control.json` uses the exact `planId` and action `pause` or `cancel`. It is checked initially and after every verified segment. Stops hold at measured joint clearance; pause requires a new reviewed remaining-path plan/session and never resumes the claimed run. These are not emergency stops.

Each plan ID claims `automation/evidence/paste-air-<id>/` before queueing. `report.json` records plan/session, exact raw path, immutable snapshots, all retained responses, native completion separately from controller-position verification, progress and failures. Existing claims forbid replay. Errors latch without speculative recovery motion. The stopped executor/busy marker guards reviewed and busy-sensitive paths, not arbitrary direct submissions. Physical inspection and separately reviewed recovery remain necessary after faults.

## Wet coupon work remains blocked

No native wet runner is implemented. Fork B rotation is not automatically equivalent to OpenPnP's bounded/inverted N2 rotation axis. Before implementing coupon extrusion, verify live firmware/settings and motor current, direction, native B mapping/limits and no unwanted articulation, syringe stroke, priming, dose/retraction/dwell and abort behavior. Complete two supervised air runs with camera evidence and observed cooperative stops first. No hardware success is claimed by this integration.

## Live quarantine status

The parent applied and independently read back the no-motion N2 quarantine at 10:50 UTC on 2026-09-25, while OpenPnP was disabled/unhomed. See the [applied record and restore limits](../operations/paste-commissioning.md#applied-no-motion-quarantine-1050-utc). Saved configuration hashes remain unchanged; normal exit may later persist the live state, so inspect after every restart. This does not release installation or physical execution gates.


## Native connection inspection after USB enumeration changes

`python3 automation/scripts/paste_serial_preflight.py` checks the exact recorded STMicroelectronics Marlin USB identity without opening the device. It reports only owner PIDs and process names, never browser content or process arguments. Exit 0 means no owner was observed at that instant; 2 means owned; 3 means missing/inconclusive. An existing browser Web Serial connection must be released before OpenPnP connects. Do not kill an unknown owner to force access.

`Connect_Inspect_Paste_Controller.js` is a staged reviewed native-owner diagnostic, not an enabled machine or an air run. It verifies the installed driver binary, live command/settings contract, disabled/unhomed/stopped state, N2 quarantine, exact device and absence of serial owners. After hash-verified private disk/live backups it changes only the in-memory port name to the stable by-id identity, then connects the existing OpenPnP GcodeDriver. This native connect changes G-code units/mode with G21/G90 and initializes VAC sensors with the audited M260 sequence; it is not described as a purely read-only serial operation. The inspected native connection path sends no move/home/motor-enable/disable command. USB connection can reset a controller, so homing remains invalid.

Only fixed M115/M503 queries follow; firmware identity/settings payloads, errors, resets and resends are checked and recorded. No M906 command was added: official source confirms no-parameter reporting, but the precise flashed binary provenance is not established. M503 may already report current settings. The driver disconnects in `finally`, with both native port closure and reader-thread termination verified rather than trusting its connected flag. No retry, `cfg.save()`, machine enable/home, native task-queue flush, motion or second serial connection is issued. Normal OpenPnP exit may persist the corrected in-memory port. This diagnostic's policy tests and Nashorn compilation are software checks; actual controller results must be recorded separately after parent/operator review and exclusive ownership.

## USB overview stills and image matching

`capture_usb_overview.py` accesses only the separate EMEET overview camera. First inspect its current preview PID, then run the default read-only preflight:

```sh
python3 automation/scripts/capture_usb_overview.py --preview-pid CURRENT_PID --output /absolute/new-overview.jpg
```

After reviewing that preflight, add `--execute` to briefly stop only the exact validated preview through its process handle, acquire twelve 1920×1080 MJPEG frames, save the last frame to an exclusive new JPEG path, and restore the preview in `lumen-webcam`. The helper uses DISPLAY/XAUTHORITY observed from that preview, refuses other video owners, and reports capture/restoration separately. A failed restoration requires inspection; it never kills an unknown owner. It does not access OpenPnP, serial, the top/bottom cameras, or machine controls. A clear image is evidence for human review, not calibrated clearance or physical commissioning success.

For offline comparison of raw top-camera frames, prefer `analysis/top_feature_match.py BEFORE AFTER --reference-roi x0,y0,x1,y1 --max-shift-px 1200`. Select a distinctive feature visible in both frames and inspect the matched crops and alternatives; the ROI is in the BEFORE frame. The older whole-frame `top_raw_translation.py` can select a different repeated bed label and return a convincing but wrong displacement. Do not use its scale estimate without an independently verified feature match. Neither method establishes surface Z, camera/nozzle registration, or extruder calibration. Image evidence and derived local measurements remain in private records.

The staged [stationary N1 free-air baseline recorder](vacuum-baseline.md) samples VAC1 off/on/off through the established owner without motion. Its results require physical review and do not authorize probing or dispensing.

## Latest software additions

[Deposit mask metrics](analysis/deposit_metrics.md) provide deterministic coverage, centering, spill and bridge-candidate measurements from reviewed aligned masks. They do not infer volume or automatically approve a recipe. See the private commissioning progress record for current physical results; nominal CAD, saved registration and software tests are not new calibration.

## Staged Z observation and native fault latch

The separate [one-step Z observer](z-observation.md) remains code-disabled and has no dispatcher route. It permits only a reviewed +1 mm raw Z observation, never a surface approach or automatic return. The [native error-latch installer](error-latch-install.md) has a guarded no-motion route with private backups and exact live/disk hash bindings. The separately reviewed [read-only position barrier](position-barrier.md) verifies the new configuration and reported stationary state. Installing its in-memory regex does not enable either motion adapter or establish physical calibration.
