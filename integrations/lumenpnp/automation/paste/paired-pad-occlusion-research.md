# Paired top-camera pad occlusion observations

This source-level note describes a supervised scrap-board paste experiment.
It omits private images, machine profiles, positions, session identifiers,
and controller reports. The Python CLI in this directory compares completed
baseline and after-image batch reports; it performs no machine action.
It requires Pillow. A local read-only invocation is:

    python3 automation/paste/compare-operator-pad-occlusion.py \
      --baseline path/to/baseline/report.json \
      --after path/to/after/report.json --refs R1 R2

The probe identifies two central bright metal regions in each baseline
1920 × 1080 top-camera frame, aligns the after frame by a small pixel
translation, and counts baseline bright pixels that became dark. Each
candidate's newly dark fraction is normalized by its own baseline bright
area. The output includes image hashes and pixel centers. These candidates
are identified in image coordinates and are not asserted to be board pad
numbers.

| Scrap observation | Newly dark fraction of baseline bright pad area |
| --- | --- |
| Repeated 90-degree dose, 9-degree retract, eight resistor pads | 0.91–0.98 |
| Same command on a later 20-pad sequence, first eight pads | 0.15–0.28 |
| Later part of that 20-pad sequence | Increased progressively to 0.93–0.95 |
| Startup-conditioning ABBA, first two main groups | 0.92–0.98 |
| Startup-conditioning ABBA, final two main groups | 0.98–1.00, with visible overspread/stringing |
| 40-degree dose, fixed 9-degree retract, 1-second dwell, four resistor pads | 0.93–0.99, with visible tails |
| 40-degree dose, fixed 9-degree retract, zero dwell, eight different diode pads | 0.49–0.70; a connecting strand remained |
| 40-degree dose, fixed 15-degree retract, zero dwell, four diode pads without new conditioning | 0.81–0.96; first pair had a long carried loop, second pair looked more separate |
| Same main command after four 0.25-degree sacrificial doses, four other diode pads | 0.77–0.87; main pads looked separate without long tails, while a sacrificial pair caught a large loop |

Three untouched neighboring-pad controls in the paired images measured
0.18–0.77% newly dark. Varying the red-channel difference threshold from
50 to 90 levels did not erase the large separation between a high-coverage
and a low-coverage example. This supports using the metric to flag obvious
transfer changes under this specific lighting and framing. Saturated bright
pad coverage cannot quantify additional outside-pad spread. Blue board
traces, glare, and dark paste also confound automatic bridge detection.

The ABBA order, accumulated pressure, time, and target positions were not
independently randomized. The zero-dwell and 15-degree-retract comparisons
used different positions and later pressure states. The apparent improvement
after tiny sacrificial doses covered only four main pads; those sacrificial
doses themselves produced a large strand. These observations do not
establish a causal conditioner, dwell, or retraction setting, deposited
volume, electrical clearance, reflow outcome, or a production recipe.
Review the actual before/after images for every candidate.
