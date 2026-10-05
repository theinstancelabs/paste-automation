# Existing-console survey and experiment runner

`automation/scripts/Run_Paste_Operator_Batch.js` reads
`automation/plans/operator-batch-request.json`. Dispatch it once through the existing
OpenPnP scripting/automation path, with the updated experiment console visible.
It calls that console's API; it never creates a second controller or serial connection.

Example request (replace the profile ID with the current private profile ID):

```json
{
  "schema": 1,
  "enabled": true,
  "id": "unique-baseline-001",
  "profileId": "CURRENT_PROFILE_ID",
  "mode": "survey",
  "references": ["R21", "R22"]
}
```

`survey` moves the top camera to each registered R or D component center and captures PNGs. It does
not dispense. Reference order is preserved. R1–R40 and D1–D40 are accepted only when present in the current registered profile. `dispense-and-survey` additionally
requires a recipe and performs the complete selected group without pausing for
images between pads. It then photographs the selected resistors.

Use `automation/paste/prepare-operator-experiment.py` to author and validate a
unique request. A survey preview is:

```sh
python3 automation/paste/prepare-operator-experiment.py survey --refs R22 R23
```

For a dispense preview, supply each recipe value explicitly; this command only
writes a uniquely named request and reports its plan:

```sh
python3 automation/paste/prepare-operator-experiment.py dispense-and-survey \
  --refs R22 R23 --dose 20 --push-deg-s 16 --retract-percent 0 \
  --retract-deg-s 100 --dwell-ms 0 --retract-dwell-ms 0 --gap-mm 0.2
```

The author checks the current profile, calibration and gross-travel ledger
against the operator policy. Adding `--execute` is a separate explicit step:
it acquires a lock, rechecks that evidence, stages the request, and dispatches
it once through the reviewed action path. Do not use it as a preview flag.

```json
"recipe": {
  "doseDegrees": 20,
  "retractPercent": 0,
  "dwellMs": 0,
  "retractDwellMs": 0,
  "bSpeedFraction": 0.16,
  "retractSpeedFraction": 1,
  "workZ": 60,
  "heightMode": "gap",
  "gapMm": 0.2,
  "padMode": "both"
}
```

These values illustrate request syntax, not a validated production recipe.
Dose is motor degrees per pad. Speed fractions use the configured B-axis rate;
at the reviewed 100 degrees/s setting, 0.16 is 16 degrees/s. Retraction speed
is independent; restoring pending retraction uses push speed.

Gap mode commands raw Z = touchRawZ − gapMm for each pad. In the current
counterbalanced geometry, a confirmed N2 native touch Z4.6 maps to raw Z58.4;
a 0.2 mm commanded gap means raw Z58.2 / native N2 Z4.8. This is a distance
above the operator's touch reference, not an independent surface measurement.
An operator-confirmed coplanar scrap reference assumes the PCB shares that
height; it does not measure PCB tilt. Board movement requires fresh XY alignment.

Each unique ID creates `automation/evidence/operator-batches/<id>/report.json`
and resistor PNGs. An existing ID is rejected rather than replayed. The report
contains the request, native action IDs, capture positions and any failure.
The UI STOP button interrupts the current action using the existing controller
policy and also prevents subsequent actions, including when pressed between
camera moves. Failures stop the runner without retries. A software completion
record means motion was verified; deposit quality still requires image review.

The runner deliberately retains the controller's current clearance and stage
verification behavior. Current measurements show approximately 5.3 seconds
per pad, dominated by repeated full clearance Z travel, not agent decisions.
Any lower local travel plane requires separate clearance validation for both heads.

Optional `conditioning` contains `references` and its own `recipe`. Those references
must be distinct from the main group. The runner dispenses this sacrificial group,
then starts the main group without intervening image inspection. Both groups are
photographed afterward. Each group retains normal clearance and controller checks.

The CLI supports `--condition-refs R31 --condition-dose .25`. It copies the main
recipe's push speed and gap but sets conditioning retraction and both waits to zero.
Its preview includes gross travel for both groups and pending retraction between
them. No extrusion occurs during preview; `--execute` dispatches the prepared
request once through the existing reviewed-action mechanism.

## Optional paired-pad hop

The default plan keeps its existing full-clearance moves. To enable a bounded
hop only between two pads of the same reference, pass `--paired-pad-hop-mm`
with `--pad-mode both` and use the measured-touch gap profile. The planner
requires both measured touch Z values, pair separation no greater than 3 mm,
touch-height difference no greater than 0.10 mm, and a 0.50–2.00 mm hop on a
0.05 mm grid. Per-pad retraction cannot be combined with this option. The hop
raises by the requested amount from the lower raw work-Z value, crosses only
between the two pads of that same reference, and returns to safe Z before the
next reference and at the end. Preview rejects invalid geometry or heights.

Example recipe used for the R36–R38 trial (those references are already used;
this is a record, not a rerun instruction):

```sh
python3 automation/paste/prepare-operator-experiment.py dispense-and-survey \
  --refs R36 R37 R38 --pad-mode both --dose 35 --push-deg-s 16 \
  --retract-percent 20 --retract-deg-s 100 --dwell-ms 2000 \
  --retract-dwell-ms 500 --gap-mm 0.2 --paired-pad-hop-mm 0.5
```

References are required explicitly. The CLI does not detect occupied/used pads,
automatically skip them, or substitute targets. Before execution, select fresh
unused references from a current survey and check the preview; never reuse the
R36–R38 example group. Preview creates a unique request and does not move or
dispense; `--execute` remains a separate explicit dispatch step. Image review
and root approval are still required before treating a run as physically
accepted.

For an explicit per-pad pressure-relief experiment, add recipe
`"retractEachPad": true`, or CLI `--retract-each-pad`. The default remains false.
Enabled mode retracts immediately after each dose, before lifting, then restores
that tracked amount before the next dose (including the other pad of the same
component). It does not also apply the old end-of-pair retract. Example: four pads
at 100° with 10% relief consume 470° gross from zero initial pending relief and
leave 10° pending. This is experimental behavior, not verified deposit quality.

Camera inspection waits 150 ms after a verified jump, checks the machine remains
idle at the same pose, discards one captured frame, then saves the next frame.
STOP and unchanged-pose checks surround this capture sequence. This settling is
only for the survey after dispensing; it never inserts a pause between doses.

### Experimental conditioned 30° preset

Preview with explicit sacrificial conditioning and main references:

```sh
python3 automation/paste/conditioned-30deg.py --condition-refs R1 --refs R2 R3
```

Choose appropriate registered, available pads; the references above are examples,
not a claim that those pads are clean. Add `--execute` to dispatch once through
the existing operator runner. Preview performs no motion. Main settings are 30°
per pad, 50°/s push, 10% retraction after each pad at 100°/s, 1 s dose dwell,
zero retraction dwell, and 0.1 mm commanded gap above the confirmed touch reference.
Conditioning uses 0.25° per pad with zero waits/retraction. It **also restores any
tracked pending retraction**, so the first conditioning action can advance more
than 0.25°. The gross preview includes this restoration.

Conditioning and the main group execute consecutively without agent inspection
between them. Startup conditioning remains experimental: one conditioned group
worked, while a later startup left a large strand on the first component before
subsequent deposits separated. This is not repeated qualification or an automatic
needle-cleaning guarantee. Survey images are saved after the complete batch.

The conditioned preset also accepts an explicit `--dose` from 0.25° through 120° (for example `--dose 60`);
the default remains 30°. All other settings and conditioning behavior are unchanged.
A requested dose is not a general component-volume calibration; the existing planner still validates its grid and gross budget.
