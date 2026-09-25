# Commissioning and handoff

Status: **not run on hardware**. The current task began in PCB Expert; implementation files are in the local LumenPnP Autonomy project, under `paste-automation/`. Changing filesystem working directories does not move the chat between ChatGPT projects.

## Carry forward established automation lessons

The existing `../lumenpnp-handoff/PROJECT_HANDOFF.md` and `../PHASE_1.md` require an explicit origin/units/count audit, a separate test job and settings backup, physical registration, distant/asymmetric camera checks, clearance proof, supervised air cycles, pause/stop verification, and reproducible saved results. Local records do not establish that those physical gates were completed.

## Installation while software is prepared

- Follow the actual right-toolhead kit mounting instructions. Confirm machine and board revision before wiring. The B rotation motor path is repurposed for paste; placement routines must not treat it as an available pickup nozzle.
- Preserve working OpenPnP files and controller/EEPROM settings. Record firmware identity and actual motor current before considering changes. No firmware flash is currently justified by the source review alone.
- Measure clearance of both heads, syringe, cables, board, clamps and feeders over the intended path. Shared Z motion makes checking only the syringe insufficient.
- Measure tip offset after final mounting and board registration after clamping. Retain direction, tip gauge, material and measured surface height with the job.

## First run gates

| Gate | Evidence required | Status |
| --- | --- | --- |
| Machine identity | hardware/controller revision, firmware identity/settings, OpenPnP version | Pending |
| Installation | right motor connector, motor rating/current, mechanical clearance, needle/syringe | Pending |
| Coordinate provenance | exact PCB revision/side, origin, Gerber/pad count, measured registration | Pending |
| Profile | bounds, safe Z/direction, dispense Z, XY offset, conservative feeds | Pending |
| Air run 1 | all targets at clearance, no B movement, no collision, observed pause/cancel | Pending |
| Air run 2 | repeat from reviewed snapshot, exported record | Pending |
| Coupon | direction, priming, dose/retract/dwell, dot consistency, remaining syringe stroke | Pending |
| PCB dispensing | camera-verified distant targets and recorded result | Pending |

Pause/cancel only stop after the current point and lift complete. A firmware or transport fault aborts further host commands without speculative recovery moves; previously buffered work may still execute. Use the machine's physical stop procedure when immediate interruption is required. Re-home/re-register as appropriate after recovery; do not automatically repeat a possibly dispensed point.

## Transfer to the ThinkPad

Fork created at `https://github.com/theinstancelabs/paste-automation` through `aabdel0181`; upstream history is preserved. Clone that fork on the ThinkPad; install dependencies, run tests and build, then transfer private measured profile/job files separately. Hardware-dependent calibration is not bundled as a guessed profile.

## Outstanding engineering work

This first implementation provides a checked execution and offline-planning path, not a completed unattended production system. Next hardware-dependent work: confirm actual firmware/baud/current, measure machine profile, verify cooperative controls, establish syringe stroke/dose/feed limits, adapt automatic camera calibration to the measured profile, and integrate with the existing machine owner's API on the ThinkPad. No serial bridge has been deployed and no remote machine connection is established.

## User-confirmed target (2026-09-25)

LumenPnP v4.1 with the latest official extruder, installed on nozzle 2. This identifies the machine family; installed firmware, current, exact extruder revision and all measured clearances remain to be recorded. Requested GitHub owner is InstanceLabs; the existing handoff uses the `theinstancelabs` organization. Preferred contributor is `aabdel0181`, with another authorized account acceptable.
