# Motor-driven paste dispensing: commissioning observations

## Commissioning update — 2026-10-04

Later trials supersede the early trial context below. Four eight-pad resistor
runs used 90° nominal dose, 50°/s push, 1 s dwell, 0.1 mm commanded gap, and
fixed retraction after every pad at 100°/s. The compared relief amounts were
6°, 9°, and 13.5°. All 32 target pads showed visible deposits in post-run images.
There was no clear stringing winner among these settings. These are 2D visual
observations, not measured volume, 3D shape, shorts testing, or reflow qualification.
A second independent eight-pad run at 9° relief also showed substantial, broadly
similar deposits on all eight targets, with no missing dots or definite bridges.
The two 9° runs therefore provide 16 visible deposits at the same settings.
The current candidate is 90° dose, 50°/s push, 9° (10%) relief after each pad at
100°/s, 1 s dwell, and 0.1 mm commanded gap. Volume and reflow remain unqualified;
idle ooze remains unresolved.

Sacrificial conditioning before the uninterrupted group was critical to managing
idle buildup: earlier startup strands contaminated the first component, while
waste touches kept that buildup away from the subsequent resistor sequence.
This does not demonstrate autonomous needle cleaning. Conditioning restores
tracked pending relief before its small new dose; its movement is not merely the
nominal conditioning dose. Keep this startup behavior explicit in comparisons.

A fresh firmware query found B200 mA despite an earlier runtime B400 mA command;
a separately reviewed stationary change then verified B400 mA before these runs.
Recheck current after power cycles. Firmware positions and step counts establish
commanded controller motion, not actual shaft rotation or delivered paste volume.
The repeat supports this candidate for further validation, not a universal component recipe.

