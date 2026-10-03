# OpenPnP paste experiment console

Open **Scripts → Paste_Experiment_Console**, or run:

```sh
python3 /home/lumen/lumenpnp/automation/scripts/run_reviewed_action.py paste-operator-console --confirmed
```

Opening replaces an idle older console and performs no motion. It uses OpenPnP's existing connection. It never opens another serial controller, homes, primes, changes motor current, or runs a pickup/tool-change routine.

## Enable camera controls

Check **I am watching…**, then click **Connect/check controller**. This verifies the existing controller without moving. The status line explains whether controls are disarmed, busy, ready, or awaiting calibration. Camera/calibration buttons become available after the check; dispensing additionally requires XY and height calibration. Errors appear in the log. An uncertain controller response quarantines the session without retry.

## Replaced or moved board

Click **Board replaced / Reset calibration** whenever the board is replaced, removed, or moved. This immediately invalidates dispensing calibration. Initial use also starts uncalibrated.

1. Select **R1**, click **Camera Center**, then use camera **X/Y −/+** jog buttons to center the view between its two copper pads. Click **Record aligned center**. Repeat for **R15** and **R40**, then **Apply 3-point XY**.
2. For each of those three resistors, select it and use **Approach selected Pad 1 (no paste)**. Start at raw Z **55** and inspect before lowering further. Increasing raw Z lowers the needle. The input accepts 0.05mm steps; XYZ speed remains 100%. Each approach first lifts to clearance and positions XY, then descends. Do not use the old surface as a measured height for the replacement board.
3. Physically measure the needle-to-board gap at that position. Enter it in **Measured needle-to-board gap**, then **Record measured gap**. This records the actual controller pose and your measurement; it is not an automatic vacuum/load-cell probe. Repeat at R1, R15, R40.
4. Click **Apply 3-point Z**, then **Lift both heads to clearance**. The fitted surface retains at least 0.30mm uncertainty and a 0.10mm conservative clearance; the maximum work Z automatically becomes shallower if the measurements require it. The recipe Work Z field follows that limit.

The console fits a three-point affine alignment and a three-point height plane. It preserves the installed camera-to-needle offset; it does not recalibrate that offset. Three points give an exact fit, not an independent accuracy check: inspect another separated resistor with the camera before dispensing. Incorrectly identified pads or guessed gaps are not valid calibration. Targets outside the established machine/head envelope are rejected rather than expanding the envelope. Large board relocation or a changed needle/head requires an updated machine profile.

Calibration measurements persist locally across reopening within the same bound session. Reset them explicitly after physical board movement. A power cycle, homing change, different job, or configuration change requires renewed session evidence; the panel does not silently adopt it. No OpenPnP job or saved machine configuration is rewritten by this local paste calibration.

## Experiment

Select a resistor or Ctrl/Shift-select a group. Groups run in displayed numeric order. Set dose, inter-resistor retraction, dose/retraction dwell, extrusion-axis speed, and work Z. **Both pads**, **Pad 1 only**, and **Pad 2 only** immediately dispense on the selection. Use camera buttons for inspection afterward. **Save recipe** records your settings and selected group; **Load recipe** never moves.

Defaults are exploratory: 6° per pad, 15% inter-resistor retraction, 2000ms dose dwell, 500ms retraction dwell. There is no retraction between the two pads of one resistor. Pending relief is restored immediately before the next dose, including across button presses. Extrusion speed 0.05 means 5% of the configured B-axis speed; XY/Z remain at full speed.

There is no automatic priming or tip cleaning. Inspect the tip and use a sacrificial pad for operator-controlled priming before comparing deposits. Keep initial pressure and timing consistent.

**STOP after current move** is cooperative: it finishes the active controller operation, then lifts to clearance. Use the physical emergency stop for an immediate stop.

This profile supports the current FTP demo's R1–R40. It is not an arbitrary KiCad importer or a qualified production recipe. Run records and measured calibration stay private under `automation/evidence/operator-paste-runs/`; recipes are in `automation/evidence/operator-recipes/`. Reusable source is exported to the public integration repository; the separate viewer remains private.
