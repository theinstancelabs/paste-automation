# OpenPnP paste experiment console

Launch from OpenPnP **Scripts → Paste_Experiment_Console**, or from the machine terminal:

```sh
python3 /home/lumen/lumenpnp/automation/scripts/run_reviewed_action.py paste-operator-console --confirmed
```

Opening the console does not move, home, prime, change current, or dispense. It uses OpenPnP's existing controller connection. Do not open another serial controller.

1. Select a resistor. Ctrl/Shift selects several; groups run in displayed numeric order.
2. Confirm that you are watching, the board has not moved, the selected pads are usable, and the area is clear using the checkbox.
3. Use **Camera Pad 1 / Pad 2 / Center** to inspect the selected resistor in OpenPnP's camera view.
4. Set dose, retraction, dwell and extrusion motor speed. **Both pads** dispenses on each selected resistor; the single-pad buttons address only that pad. These are immediate machine-action buttons.
5. Inspect with the camera buttons. Save promising settings with **Save recipe**. Each run also records its recipe, pad order, verified motion and outcome under `automation/evidence/operator-paste-runs/`.

The initial values reproduce the exploratory 6° dose, 15% inter-resistor retraction, 2000 ms dose dwell and 500 ms retraction dwell. They are **not a qualified production recipe**. There is no retraction between the two pads of one resistor; inter-resistor retraction is restored before the next dose. XY and Z remain at full configured speed. Motor speed is a fraction: `0.05` means 5% of the configured extrusion-axis speed, independent of XY/Z.

**Work Z** is the existing machine coordinate: larger values lower the needle. The panel checks each pad against the retained provisional surface model and rejects insufficient clearance. Rod exposure is a remaining-stroke estimate, not a measurement of needle clearance or paste volume.

**STOP after current move** is cooperative, not an emergency stop. It takes effect between completed controller operations. For immediate danger, use the machine's physical emergency stop. A communication fault latches the session; the panel does not retry or clear controller quarantine.

The supplied local profile contains the current FTP demo's 40 resistor pairs and registration. It is not a generic KiCad import. Loading another job, restarting OpenPnP, moving the board or changing the head requires a refreshed profile/registration. Do not re-arm the unchanged-board checkbox after moving the board.

Recipes can be loaded without movement. There is no automatic priming or tip cleaning: use a sacrificial selected pad for operator-controlled priming, and inspect the tip before comparison runs. Keep the same starting pressure and timing when comparing settings.

Local profile and run records stay private. Reusable UI/backend source belongs in the public integration repository; the separate web viewer remains private.
