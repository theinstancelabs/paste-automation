# OpenPnP paste experiment console

Open **Scripts → Paste_Experiment_Console**, or run:

```sh
python3 /home/lumen/lumenpnp/automation/scripts/run_reviewed_action.py paste-operator-console --confirmed
```

Opening replaces an idle older console and performs no motion. It uses OpenPnP's existing connection. It never opens another serial controller, homes, primes, changes motor current, or runs a pickup/tool-change routine.

## Enable camera controls

Check **I am watching…**, then click **Connect/check controller**. This verifies the existing controller without homing or issuing a new move. It rebinds only a healthy, idle executor owned by OpenPnP. If an operator-issued manual jog is still pending, it waits for that jog with the configured M400, obtains fresh position with M114, verifies B against the existing dose ledger, and adopts the stationary pose without resetting the budget. The status line explains whether controls are disarmed, busy, ready, or awaiting calibration. Camera/calibration buttons become available after the check; dispensing additionally requires XY and height calibration. Errors appear in the log. An uncertain controller response quarantines the session without retry.

## Replaced or moved board

Click **Board replaced / Reset calibration** whenever the board is replaced, removed, or moved. This immediately invalidates dispensing calibration. Initial use also starts uncalibrated.

1. Select **R1**, click **Camera Center**, then use camera **X/Y −/+** jog buttons to center the view between its two copper pads. Click **Record aligned center**. Repeat for **R15** and **R40**, then **Apply 3-point XY**.
2. For each of those three resistors, select it and use **NEEDLE Approach Pad 1 (no paste)**. Start at raw Z **55** and inspect before lowering further. Increasing raw Z lowers the needle. The input accepts 0.05mm steps and is capped by the profile's separate reviewed calibration raw-Z limit and head-clearance bounds; this limit can exceed the dispensing work Z. XYZ speed remains 100%. Each approach first lifts to clearance and positions XY, then descends. Do not use the old surface as a measured height for the replacement board.
3. After reset, the no-gauge height workflow is to select R1, R15, and R40 in turn; use **NEEDLE Approach Pad 1**, watch the needle, and record only when the metal needle is barely touching. Confirm each touch, then lift before moving to the next resistor. After three confirmed touches, click **Apply 3 needle touches**. The commanded gap defaults to **0.20 mm above the fitted touch plane**. This workflow needs no vacuum plane or feeler gauge.
4. The separate vacuum-assisted workflow captures relative board slope, then records one explicit bare-needle touch at the selected Pad 1. Vacuum estimates slope only; it does not detect contact or establish absolute height. A manual alternative is to physically measure gaps at R1, R15, and R40, record them, and apply the three-point Z fit. Click the matching **Apply** action, then **Lift both heads to clearance** before dispensing. Replacing, removing, or moving the board and clicking **Board replaced / Reset calibration** invalidates saved alignment and height references. Recalibrate after any such change.

The console fits a three-point affine alignment and a three-point height plane. It preserves the installed camera-to-needle offset; it does not recalibrate that offset. Three points give an exact fit, not an independent accuracy check: inspect another separated resistor with the camera before dispensing. Incorrectly identified pads or guessed gaps are not valid calibration. Targets outside the established machine/head envelope are rejected rather than expanding the envelope. Large board relocation or a changed needle/head requires an updated machine profile.

Calibration measurements persist locally across reopening within the same bound session. Reset them explicitly after physical board movement. A power cycle, homing change, different job, or configuration change requires renewed session evidence; the panel does not silently adopt it. No OpenPnP job or saved machine configuration is rewritten by this local paste calibration.

When the operator has already issued a manual jog and its completion is still pending, the read-only position barrier can be run with `capture-manual-home-position.py --operator-home-confirmed --manual-jog-completion-confirmed`. The second flag explicitly permits only the configured native **M400** completion wait, followed by a fresh **M114** position query. It does not issue a jog or home command; leave it off for ordinary stationary reads.

## Experiment

Select a resistor or Ctrl/Shift-select a group. Groups run in displayed numeric order. Set dose, inter-resistor retraction, dose/retraction dwell, extrusion-axis speed, and work Z. **Both pads**, **Pad 1 only**, and **Pad 2 only** immediately dispense on the selection. Use camera buttons for inspection afterward. **Save recipe** records your settings and selected group; **Load recipe** never moves.

Defaults are exploratory: 6° per pad, 15% inter-resistor retraction, 2000ms dose dwell, 500ms retraction dwell. There is no retraction between the two pads of one resistor. Pending relief is restored immediately before the next dose, including across button presses. Extrusion speed 0.05 means 5% of the configured B-axis speed; XY/Z remain at full speed.

There is no automatic priming or tip cleaning. Inspect the tip and use a sacrificial pad for operator-controlled priming before comparing deposits. Keep initial pressure and timing consistent.

**STOP after current move** is cooperative: it finishes the active controller operation, then lifts to clearance. Use the physical emergency stop for an immediate stop.

This profile supports the current FTP demo's R1–R40. It is not an arbitrary KiCad importer or a qualified production recipe. Run records and measured calibration stay private under `automation/evidence/operator-paste-runs/`; recipes are in `automation/evidence/operator-recipes/`. Reusable source is exported to the public integration repository; the separate viewer remains private.
