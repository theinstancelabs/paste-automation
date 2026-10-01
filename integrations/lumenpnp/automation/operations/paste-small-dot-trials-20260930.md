# September 30 paste commissioning observations

Physical flow was observed at the right needle and on the raised blue scrap after the current restart's 960 degrees of negative B travel. The previous syringe ledger retains 10,940 degrees plus unknown manual displacement; a controller restart does not reset syringe consumption. Motor current remains the observed 200 mA. No firmware flash was performed.

A separate 2-degree negative dose at raw X298.48, Y305.3, Z57.75 followed by a 2-degree positive retraction left a blob and a long connected tail on the scrap. This trial is rejected for resistor-pad use. The long software preparation interval between the dose and retraction confounds dose-versus-volume inference. Two-dimensional images do not establish delivered volume.

A copied report-directory prefix initially caused the Python waiter to time out despite verified completion. The existing terminal report and ledger were recovered before further action; the dose was not replayed. Subsequent stroke reports use the corrected commissioning prefix.

A further 20-degree positive pressure release completed at clearance. The next trial is prepared at a clean neighboring round pad, raw X293.33, Y305.3, Z58, B-220, with a manual oblique-image gap estimate of 0.65 +/- 0.30 mm. This is a scrap trial measurement, not demo-board Z calibration. All commanded XY and Z moves retain native speed fraction 1.0; B dosing has a separate rate. The stationary camera LED was restored after the power cycle.

The controller-owned dispense/dwell/retract/lift path is now implemented and completed its first scrap-pad cycle below. Physical deposit acceptance and repeatability still need inspection; no resistor-pad recipe or demo-board completion is claimed. Fresh board registration and separate demo-board height evidence remain required; preserve the earlier placement flags and calibration records.


The first controller-owned cycle completed as report `7e40e49f-aaa4-45f4-984d-dadefab9773f` at the clean scrap pad. It applied a 20-degree B dose, 200 ms dwell, 2-degree positive B retraction, then a 5 mm raw-Z lift at native speed fraction 1.0. All three native stages and controller counts verified; the final raw pose was X293.33, Y305.3, Z53, A720, B-238, with no uncertain completion. This verifies the software motion cycle only; physical deposit acceptance remains pending visual inspection. The session's charged signed-stroke gross is 46 degrees.


The 20-degree timed cycle was rejected after top-camera inspection: the deposit exceeded the 1.6 mm scrap pad and overlapped earlier paste. Two subsequent 4-degree dose / 200 ms dwell / 2-degree retract / 5 mm lift cycles completed with exact controller verification, reports `56b8a53f-4385-4c7b-a0a4-8a20864f08e6` and `10931100-730d-4b54-9ca7-12bf6608ac54`. Both left isolated deposits without a bridge; their size and centroid varied, so neither establishes an accepted resistor recipe. Signed commissioning gross is now 58 degrees; last B is -242. No demo-board paste has been applied.

Oblique image review exposed a limitation in the earlier manual gap numbers: lateral motion changes projected image Y. Constant image-Y comparisons cannot prove a precise gap, Z drift, or contact. The earlier estimated gap values are provisional and must not be promoted to calibrated surface heights. A QFN top-camera image was acquired for independent feature matching; its wide-view corner correspondence remains insufficient for precision metrology.
