# Independent integration review — 2026-09-25

Software staging passed independent review. Physical commissioning has not occurred, and `Run_Paste_Air.js` retains its hard execution gate set to `false`.

## Checks actually run

- `/home/lumen/paste-automation` HEAD is `c497bfbef2f7347538966c129bf7ac7bdc2c1a0f`.
- Node v22.23.2 / npm 10.9.8: `npm ci` completed, reporting zero known vulnerabilities; all 33 fork tests passed; `npm run build` passed with Vite 8.3.1. Fork working tree remained clean.
- `node --test automation/paste/safety.test.cjs`: all 13 integration tests passed, including the pinned pure planner, pending-profile rejection, native coordinate frame, bounds, session freshness, joint clearance and installation/area attestations.
- `python3 -m unittest discover -s automation/tests -p test_paste_installation_lock.py -v`: all three installation-lock tests passed. Missing, malformed and locked records block legacy reviewed dispatch; only explicit `locked: false` releases it.
- The installed Nashorn 15.4 engine compiled the staged `Run_Paste_Air.js`, `Automation_Reviewed_Command.js` and shared `safety.cjs`, including the live-configuration fingerprint refinement. Compilation used `javax.script.Compilable.compile`; none of these scripts was executed by the reviewer.
- Final `Apply_Paste_Quarantine.js` passed independent exact source review and Nashorn compilation before parent dispatch: disabled/idle/stopped and identity gates, matching disk-backup hashes and exact serialized-live UTF-8 backup bytes before mutation, audited model-only setters, verified post-state and unchanged disk hash, model-only rollback on failure. This approves that no-motion configuration operation, not physical commissioning.
- The reviewer opened neither a serial connection nor a machine-control connection, and commanded no motion, homing, vacuum, extrusion, settings query or firmware change.

These checks do not validate runtime Java method dispatch, physical travel, actual controller timing, clearance, registration or paste flow. The fork's transport tests exercise its serial implementation; the native adapter uses OpenPnP's driver instead and does not inherit hardware validation from those tests.

## Findings and resulting constraints

Installed configuration has opposing shared Z: native N2 `z2 = 63 - controller Z`. Old N1 surface Z, safe Z and the legacy N24 offsets/runout are not extruder measurements. The native B axis also has rotation limiting and linear/rotational inversion settings. Consequently the fork's raw `G92 B0` and XYZ/B plan must not be replayed through OpenPnP as if its coordinate state were interchangeable.

The adapter imports only the pinned pure planner. Its native runner submits XY through the existing OpenPnP owner from an already measured joint-clearance pose, with no initial lift, surface approach or B rotation. Every point is transformed and checked before the first move. It checks native raw axis topology, serialized live machine configuration, empty/no-tip right-head quarantine and a current-session plan hash. Claims are one-shot; faults do not trigger recovery moves or automatic replay. Native pause ends the pass at clearance and requires a new reviewed plan/session; it is not resumable fork-runner pause.

Installed-jar bytecode review used `/opt/openpnp/openpnp-gui-0.0.1-alpha-SNAPSHOT.jar` and `javap -c`:

- `AbstractHeadMountable.moveTo` substitutes NaN Z/rotation from current location before `toHeadLocation`; the staged XY call therefore preserves those requested coordinates through native transforms.
- `ReferenceNozzle.setNozzleTip(null)` changes fields and emits property/head notifications without motion. `AbstractNozzle.removeCompatibleNozzleTip` changes compatibility state without actuation. Clearing the rotation-mode offset is also a field/property operation.
- `SimplePnpJobPlanner` cannot plan without a loaded tip, and tip-change planning filters nozzle compatibility. The trivial planner skips no-tip nozzles. Null loaded tip plus empty compatibility therefore excludes N2 from these native placement planners.
- `PrerotateAllNozzlesStep` iterates planned placements, despite its name; disabling its flag is additional protection.
- **Manual tool-change bypass:** `ReferenceNozzle.loadNozzleTip` and `unloadNozzleTip` call their BeforeLoad/BeforeUnload hooks only in the automatic-changer branch. With `changerEnabled=false`, manual-location movement bypasses those hooks. Event hooks alone are insufficient. Never call `unloadNozzleTip` merely to clear the extruder's old logical tip.
- Clearing the manual change location to the millimeter origin closes that travel path: installed `assertManualChangeLocation` rejects a location equal to `new Location(Millimeters)`. Its setter only changes model state and emits a property notification.

The official [OpenPnP scripting documentation](https://github.com/openpnp/openpnp/wiki/Scripting) describes the scripting API and events. The manual-change bypass finding above is based specifically on the installed jar, not an assumption from the event names.

## Remaining deployment gates

The pending profile deliberately contains no calibrated motion values. Complete mounting first; record actual firmware/settings through the existing owner when safely available, measured right-tip/native-frame offsets, both-head joint clearance, raw/native bounds, conservative speed and fresh board/coupon registration. The user must confirm installation complete and the motion area clear before physical operation.

Quarantine must be backed up and verified in live state before enabling a runner. In-memory quarantine is not a proven persistent configuration: recheck after restart or configuration restore, and never silently restore placement eligibility while the extruder remains fitted. Do not overwrite saved OpenPnP configuration under a running process. Preserve the latest bounded N1 pickup, camera checks, placement flags and registration procedures; these are not physical clearance approval for the newly installed extruder.

The Python and JavaScript reviewed dispatchers also block legacy actions while the installation lock is active. This protects that dispatch route, not arbitrary GUI jogging, scripts invoked directly, or physical controls. Keep OpenPnP disabled until installation and clearance are confirmed.

Keep the hard execution gate closed until supervised commissioning is ready. Two recorded air passes, observed boundary stop/cancel, then a separate small coupon with verified direction/current/stroke/dose remain pending. Wet execution is not implemented in the native adapter. No firmware flash is justified merely by installation, and the referenced video has not become a completed spoken-content review.
