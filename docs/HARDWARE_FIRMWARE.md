# Paste extruder hardware, software, and firmware

Research date: 2026-09-25. These are upstream facts, not measurements or identification of the installed machine. No hardware commands or firmware changes were performed during research.

## Upstream map

| Layer | Verified source | Revision inspected |
| --- | --- | --- |
| Mechanical CAD and example | [opulo-inc/paste-extruder](https://github.com/opulo-inc/paste-extruder) | `d1aa6cda9d3e40b7f3fbe797b8b84fd1cb556d55` |
| Browser dispensing utility | [opulo-inc/paste-utility](https://github.com/opulo-inc/paste-utility) | `56c091d058915a91b1b1ed3fb917af7484d781b4` |
| Python machine API | [opulo-inc/leash](https://github.com/opulo-inc/leash) | `ebd58c3566ca1b410ce22c6858e1f2b621a117a8` |
| Motherboard firmware branch linked by official docs | [sphawes/Marlin, rev05](https://github.com/sphawes/Marlin/tree/rev05) | `7776c7322837fc6065605413f7932ee9d56458a9` |

## Hardware and mounting handoff

The upstream extruder replaces the **right toolhead**, corresponding to the user's second nozzle installation. A NEMA11 stepper drives gears and an M3 threaded rod into a 3 ml Luer-lock syringe. This is a displacement mechanism; paste flow still depends on the material, needle, trapped air, pressure buildup, and retraction tuning. The CAD initially targeted the left side: self-printed `extruder-base` and `cartridge-clamp` must preserve the mirror operation. [Hardware README](https://github.com/opulo-inc/paste-extruder/blob/d1aa6cda9d3e40b7f3fbe797b8b84fd1cb556d55/README.md)

Opulo's manufacturing assembly page documents the stepper adapter PCB, six-position Micro-Latch connector, cartridge clamp, gears, threaded rod, and plunger assembly. It is useful for checking parts and wiring, but is not a substitute for the mounting video. Its kit packing section lists 20-gauge tips, while the current utility README recommends 22-gauge 1/4-inch tips. Record the actual installed tip rather than assuming either size. [Assembly source](https://ohai.opulo.io/lumenpnp-accessories/paste-extruder/)

Before first powered operation:

1. Finish mounting with machine power removed; identify the right motor connector from the machine/version instructions before reconnecting it. The text sources inspected do not establish a universal pin-by-pin connector map for every machine revision.
2. Record machine version, motherboard revision, motor rating, tip gauge/length, syringe size, and paste product. Check that cables, gears, cartridge, and both toolheads clear the travel envelope.
3. Preserve the working placement configuration and prohibit right-nozzle pickup, rotation, and tool-change routines while the extruder occupies that toolhead.
4. Measure a safe travel Z for this installation, board surface Z, camera-to-tip XY offset, and board registration. Upstream's hardcoded Z values are examples, not calibration data for this machine.
5. Verify extrusion direction with a small supervised move after installation; prime onto a waste target, then tune small deposits on a coupon. A successful offline preview does not establish flow or clearance.

## Software and coordinate model

The utility imports paste and mask Gerbers, associates three PCB fiducials with observed machine positions, transforms pad positions, applies camera-to-tip offset, and sends G-code over Web Serial. It uses the top camera and OpenCV for fiducial finding. Its saved JSON contains placements, fiducials, calibration coordinates, dosing settings, and tip offsets. Upstream tests/documentation primarily target KiCad exports and three 1 mm circular fiducials. Captured nozzle positions already represent the tip, so adding the camera offset again is wrong. [Utility instructions](https://paste.opulo.io/help.html)

The actual upstream generator uses `G90`, `G92 B0`, XY travel, Z approach, a B-axis dispense rotation, reverse B retraction, `G4` dwell, and Z clearance. Default dispensing decreases B; an inversion setting reverses it. This reuses the right nozzle rotation axis, rather than a heated-printer E axis. Upstream has fixed clearance `Z31.5`, end park `X5 Y5`, and a single dose for every placement. [Generator source](https://github.com/opulo-inc/paste-utility/blob/56c091d058915a91b1b1ed3fb917af7484d781b4/job.js)

Leash offers a Python route to the same controller. The extrusion example homes immediately, uses hardcoded coordinates, changes B current with `M906 B400`, primes, and dispenses at stored locations. **Do not execute that example unchanged.** Its current, positions, Z, and timing are demonstration values. [Example source](https://github.com/opulo-inc/paste-extruder/blob/d1aa6cda9d3e40b7f3fbe797b8b84fd1cb556d55/sw/extrude/extrude.py)

## Firmware compatibility evidence

No dedicated extruder MCU or separate extruder firmware was found in the hardware tree. Existing Marlin axis control is the upstream software contract; there is no evidence that installing the toolhead alone requires flashing firmware.

The official developer guide links `sphawes/Marlin` branch `rev05`, with different configuration directories for different motherboards. In its `rev5-config/Configuration.h`, `J_DRIVER_TYPE` is TMC2209, `AXIS5_NAME` is `B`, and `AXIS5_ROTATES` is enabled. Default steps per unit end with `4.44` for B. The matching advanced config defaults J current to 200 and microsteps to 8. These establish upstream B-rotation support; they do not identify the user's firmware or EEPROM settings. [Official firmware guide](https://docs.opulo.io/guides/update-firmware/), [configuration](https://github.com/sphawes/Marlin/blob/7776c7322837fc6065605413f7932ee9d56458a9/Marlin/rev5-config/Configuration.h), [advanced configuration](https://github.com/sphawes/Marlin/blob/7776c7322837fc6065605413f7932ee9d56458a9/Marlin/rev5-config/Configuration_adv.h)

Two compatibility details require explicit verification:

- The inspected firmware config specifies 250000 baud, while upstream browser code requests 115200. Native USB CDC may make this distinction immaterial, but that must be established on the actual controller rather than assumed. [Serial source](https://github.com/opulo-inc/paste-utility/blob/56c091d058915a91b1b1ed3fb917af7484d781b4/serialManager.js)
- `EMERGENCY_PARSER` is commented out in the inspected rev5 advanced config. A host cancel stops future submissions; it cannot retract commands already buffered in firmware. Do not promise that an M112 sent over ordinary serial will immediately preempt queued work. Retain physical power-stop access during commissioning.

When the installed machine is available, capture its firmware identity and reported settings (for example `M115` and `M503` through the established machine connection), verify controller ownership, and compare the correct version profile before motion. Keep firmware upgrades separate unless an observed compatibility issue makes one necessary. The official downloads are version-specific. [Software downloads](https://docs.opulo.io/software-updates/)

## Automation priorities and observed upstream defects

- Serialize command ownership; reject ACK timeouts, disconnects, and firmware errors. Upstream `send()` uses assignment in its busy-response condition, clears replies after writing, and can overlap writer locks.
- Validate numeric jobs, offsets, extrusion totals, motion bounds, clearance, and calibrated coordinate provenance before execution.
- Preserve zero-valued settings during import; upstream `value || default` replaces valid zero retraction/dwell values.
- Separate captured tip positions from camera-derived Gerber positions. Recalibrate after remounting or losing home/registration.
- Provide reviewable offline plans and per-pad completion checkpoints; report uncertain completion after transport loss instead of automatically repeating a dose.
- Keep the established automation system as the single machine owner; a second browser/Python serial controller must not compete with it.

## Licensing and attribution

The browser utility is MPL-2.0. Keep its license and notices; remove upstream product branding in a redistributed derivative as requested by its README. Hardware CAD is CERN-OHL-W v2. The extruder repository's license labels software under `./scripts` although its example resides under `./sw`; this path mismatch should be clarified before redistributing that example. Leash's license identifies MPL v2.0. The new software fork should derive from the clearly licensed browser utility. [Utility license notice](https://github.com/opulo-inc/paste-utility/blob/56c091d058915a91b1b1ed3fb917af7484d781b4/README.md), [hardware license](https://github.com/opulo-inc/paste-extruder/blob/d1aa6cda9d3e40b7f3fbe797b8b84fd1cb556d55/LICENSE), [Leash license](https://github.com/opulo-inc/leash/blob/ebd58c3566ca1b410ce22c6858e1f2b621a117a8/LICENSE)

## User-confirmed target (2026-09-25)

LumenPnP v4.1 with the latest official extruder, installed on nozzle 2. This identifies the machine family; installed firmware, current, exact extruder revision and all measured clearances remain to be recorded. Requested GitHub owner is InstanceLabs; the existing handoff uses the `theinstancelabs` organization. Preferred contributor is `aabdel0181`, with another authorized account acceptable.
