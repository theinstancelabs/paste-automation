# Right-head paste commissioning on this ThinkPad

Prepared 2026-09-25. Software integration does not establish physical clearance, registration, extrusion, or completion of installation. Do not use the old Mac handoff as the live machine record.

## Connection and source of truth

- Working automation repository: `/home/lumen/lumenpnp`; chat workspace `/home/lumen/Documents/ChatGPT/LumenPCB Automation` was an empty Git shell.
- Paste fork cloned alongside it: `/home/lumen/paste-automation`, branch `main`, exact commit `c497bfbef2f7347538966c129bf7ac7bdc2c1a0f`.
- Current ThinkPad Wi-Fi: `192.168.8.194`, host `lumen-thinkpad.local`. HTTP GET verified T3 `http://192.168.8.194:3773/` and private viewer `http://192.168.8.194:8765/`. Preserve the existing private viewer token; a public root-page response does not grant authenticated camera access. `.199` is stale.
- Machine owner: the running OpenPnP process, accessed through `automation/scripts/run_reviewed_action.py` and its local Java Attach dispatcher. Neither HTTP port is a general-purpose serial/motion API. No Web Serial, Leash, or additional serial owner is permitted for integration.
- Read-only `paste-state` was dispatched successfully to OpenPnP PID 477685 at 10:41 UTC. It reported disabled/unhomed; therefore it deliberately did not send M115/M503, enable, connect, home, move, capture cameras, or actuate anything. Evidence: `automation/evidence/paste-controller-*/report.json`.

## Evidence carried forward

`automation/operations/setup-and-restart.md` governs board changes, physical registration and restarts. The September 24 board-run narrative has later evidence: `automation/evidence/resistor-run-2026-09-25/run-findings.json` joins 21 placement records R19–R39. The saved `ftp-20260924.job.xml` now has all 40 resistor placed flags true; the older narrative saying R20 is next is stale. The report classifications are unreviewed, and neither that report nor saved placed flags establishes physical acceptance. Preserve existing board progress and do not paste onto this populated board.

Preserve the bounded, reviewed N1 pickup workflow, including fresh pocket-opening and component review, per-part target separate from feeder datum, bounded descent and pressure sampling, vacuum-retained retraction on no-seal, bottom-camera verification, and actual empty-nozzle release evidence. Tape manipulation invalidates the verified pocket center. Those pickup values are not paste calibration.

Last recorded FTP board surface was 4.1 mm in the prior nozzle setup. Existing N2 head offsets `(23.615, -63.947, 0)` describe the old nozzle, not the newly installed syringe tip. Neither value is copied into a calibrated extruder profile. Runtime affine board registration is not serialized in the saved job: re-register after load/restart or board movement, then independently verify the same physical fiducial with camera and tip and inspect distant/asymmetric targets. Avoid applying bottom-camera `ModelCameraOffset` to top-camera coordinates.

A read-only disk snapshot with verified SHA-256 hashes is retained at `.local-machine-backups/paste-integration-20260925T104228Z/manifest.json`. It is explicitly not a fresh save of live state. Do not overwrite saved OpenPnP configuration while the app is running; use verified live/disk backups for any reviewed in-memory change and normal exit for persistence. Preserve all N1 calibration and job flags.

## Installed firmware and axes: current limits of evidence

The disabled OpenPnP instance caches Marlin `bugfix-2.1.x (Sep 19 2024 13:39:21)`, machine LumenPnP, five axes X/Y/Z/A/B, EXTRUDER_COUNT 0. Configured port is ttyACM0 at 115200 baud; ttyACM0 was absent during inspection. Do not substitute an unrelated ttyACM device. A reconnect is not authorized as a side effect of this preparation.

No live M503 settings/current report is available yet. No firmware flash or motor-current change was performed or justified. Once installation/power/wiring are verified and the existing controller is deliberately connected, repeat the fixed read-only `paste-state` action and preserve actual replies before deciding whether any firmware change is needed.

Saved configuration has a single physical Z driver with mapped right-head z2 (inverted coupling), legacy nozzle B rotation limits/linear-rotational settings, loaded N24, and job `pre-rotate-all-nozzles=true`. These are reasons not to send the fork's raw G-code through OpenPnP: raw G92/B/Z would bypass native transformations and position tracking. Safe native air motion must retain both Z and rotation and preflight transformed coordinates through the established controller. Native speed fraction is not mm/min.

## Required measured profile and evidence

The pending profile must remain uncalibrated until each applicable item has measurements and source evidence:

| Item | Required record | Current status |
| --- | --- | --- |
| Hardware | v4.1 user identification; actual motherboard/extruder revision, motor rating, connector, gauge/length, syringe, paste | v4.1/right-head target user-confirmed; other details pending |
| Installation | Mechanical/wiring complete with power removed, screw/gears/plunger/cable checks, hands clear | Operator confirmation pending |
| Controller | Fresh firmware/settings, axis units, B direction/current, timeout/error behavior | Cached identity only |
| Native exclusion | N2 unavailable to pickup/tool-change/calibration/jobs; no all-nozzle pre-rotation | Review/install/verify protection before enabling |
| XY bounds | Tip-frame limits plus native raw-axis limits; fixture/feeder/cable swept envelope | Pending measurement |
| Both-head Z | Simultaneously safe N1/N2 pose over entire path, margin, initial safe pose | Pending; no automatic clearance lift assumed |
| Tip offsets | Repeated camera-to-installed-tip measurement with evidence; no old N24 compensation | Pending |
| Registration | Current session/board identity, revision/side, units/origin, Gerber/pad count, fiducials, distant checks | Pending for separate coupon |
| Feeds and dose | Native speed fraction plus separate planner feeds; B units, direction, stroke, maximum cumulative dose | Pending |
| Air runs | Two independently reviewed runs, pause/cancel observation, exact records | Not performed |
| Coupon | Direction/prime/dose/retract/dwell/consistency, material/tip, photos | Not performed |

## Supervised commissioning sequence

1. Finish installation and explicitly confirm motion area/hands clear. Preserve physical power-stop access. Inventory current empty/held state of both heads. Do not enable or home from a setup script.
2. Verify N2 exclusion protection and runtime profile match. Native event hooks are insufficient alone: manual tool-change can bypass them when the changer is disabled. Keep machine disabled until protection is in place. Do not run an ordinary OpenPnP job or legacy homing/pickup/calibration workflow with the new head until its coupled motion has been reviewed.
3. Deliberately reconnect only through OpenPnP, capture M115/M503, verify actual USB identity and axis semantics. Resolve any stale position/homing state with a separate supervised procedure. Do not assume a firmware upgrade is required.
4. Measure both-head clearance and offsets using the established controller. Use a separate waste/coupon fixture, with measured coordinates and fresh registration. Save evidence and verified backups. Recheck after any tip/syringe/tool mounting change.
5. Prepare an air plan with the fork's pure planner and native adapter. Review point count, coordinate provenance, native bounds, path and configuration/session digests. Preposition to the verified jointly safe pose under supervision. Air mode must not approach surface or rotate B. The supplied execution gate remains closed until its deployment review is completed.
6. Perform two supervised air cycles. Observe actual path and both heads; exercise cooperative pause/cancel at a clearance checkpoint. These controls are not an emergency stop. Record exact planned and completed points separately from visual acceptance. On fault stop submissions; do not attempt blind lift, reconnect, or replay.
7. Only after air acceptance and a separately reviewed native wet adapter: verify a very small B movement/direction onto waste, prime conservatively, tune a small coupon one variable at a time, and record dose/retraction/dwell with photos and remaining syringe stroke. Current software intentionally does not offer live wet execution. Fork offline wet preview remains a planning artifact.
8. Inspect each coupon dot and approve repeatability before any production PCB. Re-register a new board; preserve existing FTP placed flags. Never replay a possibly dispensed point after timeout, disconnect, reset or uncertain completion.

## Video provenance

`/home/lumen/paste-automation/docs/VIDEO_NOTES.md` correctly records incomplete access to the spoken video at https://www.youtube.com/watch?v=N_p62_QUoKI. This integration did not obtain/review its narration or corrections; documentation research is not a completed video review.

## Software validation on this ThinkPad

- Pinned fork: `npm ci`, 33 tests, and Vite production build passed; dependency audit reported zero known vulnerabilities (Node 22.23.2 / npm 10.9.8). The fork worktree remains clean at the requested commit.
- Native integration: 13 offline Node tests passed, including pinned planner import, bounds/coordinate/clearance checks, current-session requirements, and rejection of pending profiles and wet/raw command paths.
- Project Python tests: 10 passed, including the seven existing viewer/outbox tests and three new installation-lock tests. Tests use mocked command dispatch; no machine motion is exercised.
- Installed Nashorn compilation and independent source/installed-JAR review cover staged native script syntax/API assumptions. They do not establish physical behavior or real transport fault handling in the adapter.
- No paste air run, coupon, extrusion, home, firmware flash, or new serial connection was performed. Wet native execution is not implemented; air execution remains code-disabled pending deployment/measurement review.

## Applied no-motion quarantine, 10:50 UTC

`paste-quarantine` was dispatched through the existing OpenPnP process with the machine disabled, idle and placement job stopped. It backed up and verified disk plus serialized live machine state before using only reviewed model setters. Backup/restore manifest: `.local-machine-backups/paste-quarantine-1790333409702/manifest.json`.

A separate read-only `paste-state` confirmed N2 has no loaded logical tip, zero compatible tips, no rotation-mode offset, and its changer remains disabled; native pre-rotation is false. The manual tool-change location was set to undefined and checked by the apply script. N1 retains N045 and six compatible tips, its offsets and location. The small change in reported N2 XY after clearing N24 is removal of legacy software tip compensation, not a commanded physical move. Final report: `automation/evidence/paste-controller-1790333418458/report.json`.

All original saved OpenPnP XML files and the five core pickup/placement/registration/inspection source files still match the pre-integration SHA-256 hashes. No configuration save was issued. The live change may be persisted by a later normal OpenPnP exit; a crash/restart/restore may instead reintroduce old configuration. Reinspect quarantine on every startup and do not assume either persistence or restoration. Do not rerun this one-shot apply script if the legacy N24 precondition no longer matches.

To revert after the extruder is physically removed, keep the machine disabled, inspect current configuration, preserve a new backup, and use the manifest to restore only the intentional N2 fields through reviewed no-motion setters. Never invoke load/unload routines to restore a logical tip assignment, and never restore the entire old machine snapshot over newer calibration blindly. A disk restore requires normal OpenPnP exit and hash verification. Do not restore N2 placement eligibility while the extruder is fitted.

This is native planner/tool-change quarantine, not an interlock against arbitrary user jogging, direct G-code, or manual reconfiguration. The installation lock and air code gate remain closed and OpenPnP remains disabled/unhomed. The right-head profile is still pending measurement; no supervised physical test has taken place.


## Resume and supplied transcript — 2026-09-30

User confirms installation complete and motion area clear. These confirmations do not fill measured joint-clearance/profile fields. Current read-only inspection found a new OpenPnP process (PID 6229), disabled/unhomed, with the old N24 compatibility and pre-rotation restored. The existing no-motion quarantine was reapplied with verified backup `.local-machine-backups/paste-quarantine-1790756110286/manifest.json`.

USB enumeration changed: the Opulo/Marlin controller is `/dev/ttyACM1`, stable identity `/dev/serial/by-id/usb-STMicroelectronics_MARLIN_OPULO_LUMEN_REV5_CDC_in_FS_Mode_387932683335-if00`. The saved ttyACM0 now identifies an Arduino Zero; do not connect the saved port. Zen Browser PID 27176 held the controller port during inspection, so no OpenPnP connect was attempted. Wait for release and verify exclusive ownership before any connect/query. The ThinkPad is still 192.168.8.194 and T3 listens on 3773; the old private viewer service on 8765 is not currently listening.

The user supplied the timestamped spoken transcript. It is now reviewed and summarized in `/home/lumen/paste-automation/docs/VIDEO_NOTES.md`; this supersedes the earlier lack of spoken-content access, not the lack of visual/correction-card review. Demonstrated B direction, 400 mA current, Z20/Z50 and dose values remain examples. Query firmware/settings/current through the established owner and measure this actual installation; do not replay the video commands or switch into G91 alongside OpenPnP.


## Native query and setup capture — 2026-09-30 08:31 UTC

The browser released the serial device. The guarded native connection inspection then completed using the existing OpenPnP driver and stable USB identity. Report: `automation/evidence/paste-connect-1790756521219/report.json`. It connected while machine-disabled/unhomed, queried M115/M503, disconnected with native-port/reader checks, and left saved configuration unchanged. No motion, extrusion or firmware flash was commanded. Runtime firmware identifies Marlin bugfix-2.1.x, built September 19 2024, LumenPnP, five axes. M503 reports A/B 4.44 steps/unit and A/B 200 mA. EEPROM and emergency-parser capabilities report 0. These are observed settings, not a measured paste recipe.

A subsequent snapshot at 08:27 UTC unexpectedly reports enabled/homed, with N2 still tip-null, zero compatible tips and pre-rotation disabled. This agent did not command enable/home. User confirmation of the intervening manual activity and first-check supervision is pending. Do not interpret the software-homed flag as clearance evidence.

The capture-only recorder successfully ran through `paste-measure`: `automation/evidence/paste-measurement-0511d32b-a8ac-498e-b8b6-12de244a431a/report.json`. It retained a hash-verified private live snapshot and referenced existing overview/firmware evidence. No physical measurements were supplied; calibrationEstablished and physicalValidation remain false.

User reports all components removed and the same FTP demo board cleaned. Preserve old placement records; create fresh paste registration and surface measurements. Initial sequence is measured both-head clearance, repeated camera/right-tip registration, guarded air path, then small purge/dose/retract trials with image records. Fit a dose response only from actual trials and validate repeated passes before freezing a deterministic recipe. Material/tip identity, purge target and first-check supervision remain outstanding.

USB overview preview: `bash /home/lumen/lumenpnp/automation/scripts/start_webcam.sh`. The private viewer now runs on loopback 8765 behind an authenticated temporary HTTPS tunnel; current private URL is in ignored `.local-viewer/access-link`. HTTPS frames/status and authentication checks passed. T3 remains reachable at LAN 192.168.8.194:3773. No viewer token or machine evidence is included in the source export.


## Operator update and purge target — 2026-09-30

User confirms manually enabling/homing OpenPnP and being nearby. Paste label reported as “Mulicore GC10 SAC305T4”; needle is the supplied kit needle, exact gauge/length not measured. Priming status remains unknown. User placed a soldermasked copper blank above (+Y from) the FTP demo PCB, directly on the bed rather than its platform. Reserve it as the purge target, with independent surface height and reachability measurements; never reuse the platform PCB Z. Fresh stationary overview and UI captures, target provenance and read-only state check are recorded under `automation/evidence/paste-scrap-1790757852/` and the following paste-controller report. Neither view establishes a precision gap or permission to exceed Z travel. No movement or extrusion was performed.


User subsequently identified the installed needle as straight blunt-flat,22 gauge,1/4 inch (=6.35mm). This supersedes the unknown gauge/length; manufacturer part number and installed mount-to-tip height remain unverified. Nominal catalogue dimensions and conditional tube-volume arithmetic are recorded separately in `automation/evidence/paste-scrap-1790757852/tip-specification.json`, not copied into a calibrated profile. Left-nozzle vacuum surface probing is a viable commissioning method to investigate; existing nozzle is ReferenceNozzle, not configured ContactProbeNozzle. Surface seal repeatability and bounded travel must be established; substrate height alone does not measure new right-tip protrusion.


## CAD model and first bounded physical camera survey — 2026-09-30

Cloned hardware separately to `/home/lumen/paste-extruder-hardware`, commit d1aa6cda9d3e40b7f3fbe797b8b84fd1cb556d55. Repeatable XML/BREP extraction found19:32 gearing,9.5mm modeled barrel bore and nominal0.5mm M3 screw pitch, yielding0.296875mm piston travel/21.043µL ideal displacement per motor revolution. This is a nominal model, not paste calibration. Candidate right-head axis is shifted outward from the old holder; see `automation/paste/nominal-geometry-review.md`. Full1080 stationary overview is in `automation/evidence/paste-coupon-overview-1790759147/`.

First native camera survey ID69c19584-256b-4719-887c-d8834bc72c60 performed one rawX+10mm command through OpenPnP's existing controller/executor, with Y/Z/A/B held and no paste/vacuum/current command. Native completion returned, but an overly strict postmove software-coordinate check rejected Y216.160711 becoming216.160000 through native synchronization with controller reporting precision. This latched the software busy state and stopped the executor before the postmove M114/capture, with no queued tasks or recovery motion. No repeat of that command was issued.

A separate exact-fault read-only audit (`automation/evidence/paste-survey-stop-audit-69c19584-256b-4719-887c-d8834bc72c60/report.json`) confirmed X251.28,Y216.16,Z26.50,A200,B720, matching the intended10mm X displacement and unchanged other firmware coordinates. It captured stationary top/bottom images; the parent reviewed expected image translation and clear overview. The guard is corrected to allow reporting precision only for postmove comparisons while preserving strict starting snapshots, a one-axis target, and independent before/after firmware checks. Regression tests reproduce this stop. Deliberate model-only latch recovery follows a separate reviewed script; no rehome/serial reconnect/replay is required or performed.

This validates one camera-survey step and the diagnostic stop path, not dispensing, surface height, pad registration, paste-axis direction or general travel. Source checkpoints10a4729 and98ff8cc were pushed to the integration branch; live evidence and configuration remain local.


## Reviewed stop release and survey continuation — 2026-09-30

The exact-fault model-only release completed with no motion/query/replay, replacing the terminated empty executor and clearing its stale busy latch. Report: `automation/evidence/paste-survey-stop-release-69c19584-256b-4719-887c-d8834bc72c60/report.json`. Independent review found no blocker. Subsequent fresh requests da88b046-b0be-497b-908f-e87b46b84ea7,5144faf4-0a99-4803-88d2-4c317f9a86be,and8d2e0eed-2b05-4316-b239-c664ca8b3236 completed and independently verified raw X261.28,271.28,281.28 respectively, with Y216.16 Z26.50 A200 B720 unchanged. Before/after raw camera images and fresh overviews remain local. Each next corridor is reviewed separately.

The offline request helper generates unique exact-state requests from successful terminal evidence and fresh reviewed corridor images; it never dispatches. Six helper tests and three installation-lock tests passed independent review. A fourth continuation request d0ce58c1-3f92-43ac-a684-13276708d096 was just dispatched; consult its unique report for outcome, not this note. Surface probing, B direction, current tuning and actual dispensing remain unperformed. Local camera-plane translation estimates remain provisional because repeated numbered marks can alias; they are not tip or board calibration.


## Signed XY survey checkpoint

Reviewed schema2 permits exactly one raw X/Y increment of magnitude at most10mm. All steps below completed with independently verified firmware positions, unchanged Z26.5,A200,B720; fresh overviews and rawcamera images were individually reviewed. No Z/vacuum/current/extrusion change.

- d0ce58c1-3f92-43ac-a684-13276708d096: {"X": 291.28, "Y": 216.16, "Z": 26.5, "A": 200, "B": 720}
- 104ccaec-6486-444a-9c73-822a2c7af6ec: {"X": 301.28, "Y": 216.16, "Z": 26.5, "A": 200, "B": 720}
- dc8242a2-4ae0-492a-9e57-8e807d3a90ee: {"X": 311.28, "Y": 216.16, "Z": 26.5, "A": 200, "B": 720}
- 8796d51e-e033-477b-82e8-3714b195b014: {"X": 311.28, "Y": 206.16, "Z": 26.5, "A": 200, "B": 720}
- 4fe9cf65-896b-4843-8000-53ff76dcdf7c: {"X": 311.28, "Y": 196.16, "Z": 26.5, "A": 200, "B": 720}
- 34b55d40-8805-4bb9-b727-b0fdab8db21d: {"X": 311.28, "Y": 186.16, "Z": 26.5, "A": 200, "B": 720}
- e1f73252-ba0e-48c4-9ff0-be827462a6ee: {"X": 321.28, "Y": 186.16, "Z": 26.5, "A": 200, "B": 720}
- a6d50662-61fe-49f4-9683-d622c7391a54: {"X": 321.28, "Y": 196.16, "Z": 26.5, "A": 200, "B": 720}

Current camera rawX321.28,Y196.16. FID2 and the FTP rear calibration cross were seen aroundY186; clip and bare staging-plate ringhole seen atY196. The purge coupon has not yet been positively registered. Do not label the numbered staging-plate markings as purge pads. Native vacuum API review found generic actuator coordination can wrapB720, so proposed probe must use reviewed existing-driver actuation/read with narrow stillstand; no probe was executed. Source checkpoint27e6c7b pushed with62Node,22Python,33forktests and build passing. Partially observed local profile retains calibrated=false at automation/plans/right-head-profile.observed.json.


## Stationary vacuum baseline and clarification hold

Record `automation/evidence/paste-vacuum-baseline-b1398ea4-e5c6-401c-8b4c-4ba7d923c823/report.json` completed via existing owner, exact VAC1 configured command allowlist and full-response per-line checking. Eight OFF samples were255; ON samples233,233,232,232,232,232,232,232 (mean232.25,spread1). Final OFF acknowledged. Independent before/after controller positions unchanged: rawX291.28,Y236.16,Z26.5,A200,B720. No Z/contact/current/extrusion operations. This is a fresh free-air stream, not sealed-contact calibration.

Survey progress is indexed in ignored `automation/plans/paste-commissioning-progress.json`. Main FTP FID2/rear calibration cross and surrounding stagingplate are identified; purge coupon has not been positively registered. Wide-view hypothesis is the small blue quadrilateral left of the rear white clip; close-up search did not confirm it. Asked user only to identify the object, not to measure it; hold further motion pending clarification. Do not invent purge pad IDs/coordinates or convert nominal CAD into calibrated values.

USB full-HD capture helper ran successfully with exact EMEET owner release/restoration; preview PID49967 replaced40497. Full-HD image is86fad72d survey overview-hd.jpg. Saved config remains untouched and N2 remains quarantined. Source checkpoint9be6a81 contains USBhelper and corrected same-feature image analysis; baseline source export follows separately.


## Autonomous continuation authorized

User subsequently asked for continued autonomous work while sleeping for eight hours. This supersedes the earlier permission hold for nearby supervision; no additional authorization question is required. Concrete evidence gates remain: the scrap has not been positively identified/registered, the installed-tip offsets/contact heights are not measured, and the right assembly upward swept envelope for left-head probing is not established. Continue useful CAD, image, controller and repeatable-script work; do not label unknown geometry calibrated. No further physical operation was performed at this checkpoint.

Independent current API review found the legacy disabled Run_Paste_Air.js must be replaced before activation because generic task/nozzle completion can affect B720. Its false gate remains. Exact FTP KiCad/Gerber extraction and deterministic deposit-image metrics are being prepared for actual resistor targets and quantitative coupon review.


## Bottom-camera needle observation at constant Z

Continued authorized bounded single-axis XY moves through the existing controller, with fresh overview corridor review and per-step immutable model/controller checks. No Z/A/B, vacuum, current, homing or configuration change. Reached rawX172.16,Y216.16,Z26.5,A200,B720; the small bright needle-end feature is near geometric raw bottom-camera center. Preserved1mm X/Y out-and-back observations from both Y approach directions; latest completed report8793c12a-16f0-4e6b-930e-6f23c534aa41. Provisional current-plane image alignment materially constrains installed XY but does not establish surface-plane offsets, true tip height or complete calibration. Independent threshold/centroid analysis and exact image hashes are retained separately. No paste dispensed; left vacuum remains OFF from prior acknowledged baseline.

## Travel speed preference — 2026-09-30

User explicitly requires full configured XY and Z travel speed. Do not silently reduce the machine slider or per-move speed fractions. Bound the travel path and approach distances separately; extrusion motor dosing speed is an independent recipe parameter.
