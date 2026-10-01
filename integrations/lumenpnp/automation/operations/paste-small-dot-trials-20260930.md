# September 30 paste commissioning observations

Physical flow was observed at the right needle and on the raised blue scrap after the current restart's 960 degrees of negative B travel. The previous syringe ledger retains 10,940 degrees plus unknown manual displacement; a controller restart does not reset syringe consumption. Motor current was the observed 200 mA at this stage; the later reviewed 400 mA comparison is recorded below. No firmware flash was performed.

A separate 2-degree negative dose at raw X298.48, Y305.3, Z57.75 followed by a 2-degree positive retraction left a blob and a long connected tail on the scrap. This trial is rejected for resistor-pad use. The long software preparation interval between the dose and retraction confounds dose-versus-volume inference. Two-dimensional images do not establish delivered volume.

A copied report-directory prefix initially caused the Python waiter to time out despite verified completion. The existing terminal report and ledger were recovered before further action; the dose was not replayed. Subsequent stroke reports use the corrected commissioning prefix.

A further 20-degree positive pressure release completed at clearance. The next trial is prepared at a clean neighboring round pad, raw X293.33, Y305.3, Z58, B-220, with a manual oblique-image gap estimate of 0.65 +/- 0.30 mm. This is a scrap trial measurement, not demo-board Z calibration. All commanded XY and Z moves retain native speed fraction 1.0; B dosing has a separate rate. The stationary camera LED was restored after the power cycle.

The controller-owned dispense/dwell/retract/lift path is now implemented and completed its first scrap-pad cycle below. Physical deposit acceptance and repeatability still need inspection; no resistor-pad recipe or demo-board completion is claimed. Fresh board registration and separate demo-board height evidence remain required; preserve the earlier placement flags and calibration records.


The first controller-owned cycle completed as report `7e40e49f-aaa4-45f4-984d-dadefab9773f` at the clean scrap pad. It applied a 20-degree B dose, 200 ms dwell, 2-degree positive B retraction, then a 5 mm raw-Z lift at native speed fraction 1.0. All three native stages and controller counts verified; the final raw pose was X293.33, Y305.3, Z53, A720, B-238, with no uncertain completion. This verifies the software motion cycle only; physical deposit acceptance remains pending visual inspection. The session's charged signed-stroke gross is 46 degrees.


The 20-degree timed cycle was rejected after top-camera inspection: the deposit exceeded the 1.6 mm scrap pad and overlapped earlier paste. Two subsequent 4-degree dose / 200 ms dwell / 2-degree retract / 5 mm lift cycles completed with exact controller verification, reports `56b8a53f-4385-4c7b-a0a4-8a20864f08e6` and `10931100-730d-4b54-9ca7-12bf6608ac54`. Both left isolated deposits without a bridge; their size and centroid varied, so neither establishes an accepted resistor recipe. Signed commissioning gross is now 58 degrees; last B is -242. No demo-board paste has been applied.

Oblique image review exposed a limitation in the earlier manual gap numbers: lateral motion changes projected image Y. Constant image-Y comparisons cannot prove a precise gap, Z drift, or contact. The earlier estimated gap values are provisional and must not be promoted to calibrated surface heights. A QFN top-camera image was acquired for independent feature matching; its wide-view corner correspondence remains insufficient for precision metrology.


Two additional 4-degree / 2-degree retract cycles at raw Z57.5 produced one misplaced blob and one missed transfer; rejected. A deterministic three-point sequence then executed the same recipe in 30 seconds at three neighboring clear scrap pads, with verified B and Z completion for every point. Top-camera inspection showed no deposits on those three pads; timing alone did not fix transfer.

The next controlled comparison eliminates B reversal: a 20-degree forward take-up stroke followed by two 6-degree forward strokes, each followed by an immediate 5 mm lift. All three controller strokes completed and raised the original signed commissioning gross to exactly 120 degrees, B=-284. Physical inspection is pending. A controller step count establishes commanded motion, not actual gear rotation or delivered paste volume. The original 120-degree phase budget is exhausted; any further dose requires an explicit reviewed extension that retains the complete original accounting chain.


The forward-only comparison transferred a roughly0.8–1.0mm isolated dot after20degrees; both6degree points remained empty. Next trial therefore used three20degree forward-only doses on observed clear pads, retaining rawZ57.5 and fullspeed immediate5mm lifts. All completed with exact controller verification, gross180degrees andB-344; physical image review pending. A separately reviewed240degree maximum retains the original120degree ledger as immutable history and original carryover unchanged. The first extended request rejected a six-digit timestamp beforequery, reservation or motion. A new immutable millisecond-format record corrected the Nashorn parse incompatibility; no dose was replayed.


Further scrap trials: forward-only20/20/20 at rawZ57.5 deposited on only the first target; repeated20/20/20 with12seconds hold deposited on only the second target. Firmware position completion does not prove motor rotation or paste transfer. Signed commissioning gross240degrees,B=-404; original prime and manual-unknown carryover preserved. Board untouched. Current was200mA at this stage, before the reviewed400mA comparison recorded below. Returned through established clear corridor to X277.85,Y305.3,Z56.75 at full native travel speed.


## Corrected target mapping and amended cycle budget

The later rectangular-pad “missed transfer” conclusions based on raw Y300.03 are superseded: that target mapping used the wrong image-Y sign. Inspection at camera X326.47, Y236.03 showed paste at the commanded locations. Those observations do not establish failed extrusion. The measured image-shift Jacobian places the intended clean rectangular pads near raw Y311, not Y300; the camera-to-needle offset remains provisional until repeated small-dot verification.

The reviewed stationary B-current comparison changed the observed setting from 200 to 400 mA. Current is now 400 mA. A hanging paste string can contaminate subsequent targets; a fresh wipe/needle-clearance check is required before interpreting a new dot trial.

The dose-cycle builder and runtime now accept the same reviewed 240/2400-degree budget amendment as individual strokes, retaining the immutable 120-degree anchor and unchanged syringe carryover. Both dose and retract are charged together before the first controller query; faults retain the reservation and cannot be replayed. A conditioning cycle of 6-degree dose, 200 ms dwell, 2-degree retract, and 5 mm lift completed with native verification (`7b6f54d8-7e50-49fe-a89b-11f06d7d9d12`). Physical dot acceptance and repeatability remain pending; this completion does not establish a calibrated dispensing recipe.
