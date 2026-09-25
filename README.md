# Paste Automation

A development fork of the [upstream paste utility](https://github.com/opulo-inc/paste-utility), based on commit `56c091d058915a91b1b1ed3fb917af7484d781b4`. Prepared in the **LumenPnP Autonomy** project for right-toolhead paste dispensing. Local development only: this revision has not been tested on a physical machine.

## Start

Use Node.js 22.12+ (tested with 24.19).

```sh
npm ci
npm test
npm run dev -- --host 127.0.0.1
```

Open the local URL in a Web Serial capable browser on the machine's computer. `npm run build` produces `dist/`. The app no longer needs the camera/OpenCV runtime to import, preview or execute a measured job.

## What changed

- Validated, pure G-code planner shared by browser and offline CLI; explicit coordinate frame and calibrated machine profile.
- Air-run default: XY traversal at measured safe Z, no B rotation or board-surface approach.
- Bounds and clearance validation of every point before writing any command; controlled feeds; no blind end park or raw pre/post G-code.
- Preview must match current job and settings before execution. Session checks are cleared after import/reconnect/run.
- Pause/cancel at completed-point clearance boundaries; firmware `M400` confirms queued motion completed. Neither control is an emergency stop.
- Serial ACK handling tolerates fragmented CRLF replies, rejects competing batches, and aborts on firmware error, timeout or disconnect. A fault requires reconnect; it never auto-replays a possibly dispensed point.
- Downloadable run record contains the exact input/profile/plan, state transitions and error. A transport fault leaves physical completion uncertain.
- Legacy fixed-coordinate jogging/calibration handlers are disabled. Measure with the established controller and transfer the registration. Do not open two serial owners simultaneously.

## Measured job workflow

1. Read [commissioning](docs/COMMISSIONING.md) and [hardware/firmware findings](docs/HARDWARE_FIRMWARE.md). Back up working machine settings first.
2. Copy `examples/machine-profile.json` outside the repo and fill in measured bounds, safeZ, direction, feeds and camera-to-tip offsets. Placeholder values are deliberately unusable; `calibrated: true` is your attestation, not a calibration routine. Keep personal machine profiles out of commits.
3. Import a job JSON. `coordinateFrame: "machine"` uses captured tip `x/y/z` with **no** camera offset. `"board"` requires measured/transformed camera `calX/calY`, plus profile `tipXoffset/tipYoffset`; `z` is measured dispense Z. Raw Gerber XY is not registered machine XY. Do not relabel a board-coordinate file as machine coordinates.
4. Gerber loading supports selecting fiducials and inspecting points, but does not complete registration in this fork. Transfer measured coordinates into the job before execution. The existing Nano's two closely spaced fiducials are not a substitute for the upstream three-fiducial workflow.
5. Choose the coordinate frame explicitly after every import, load the measured profile, keep Air run checked, and Preview. Review the full commands and point count. The run checkbox attests that homing, registration and **both** head clearances are checked in this session.
6. Disconnect OpenPnP, connect this app, review again and perform the supervised air-run procedure. Export the run record. Each repeat requires a fresh preview and session check.
7. After two successful air runs, use a small coupon job to tune dose/retraction/dwell and direction before dispensing a PCB. Uncheck Air run only for the reviewed wet job.

Settings are in mm, XY/Z feeds in mm/min, rotational B feed in degrees/min for verified rotational-B firmware, dose/retraction in degrees, dwell in milliseconds. Confirm the actual firmware semantics before use. Bounds constrain commanded endpoints; they do not model obstacles, cable sweeps, syringe stroke or remaining paste. Feed/dose ceilings must be established during commissioning.

## Offline automation

```sh
npm run plan -- measured-job.json measured-profile.json air-run.gcode
npm run plan -- measured-job.json measured-profile.json coupon.gcode --wet
```

The CLI never connects to hardware and refuses to overwrite an output file. It uses the same validation as the browser. Example job structure (coordinates omitted intentionally):

```json
{
  "coordinateFrame": "machine",
  "placements": [{"x": 0, "y": 0, "z": 0}],
  "dispenseDegrees": 9,
  "retractionDegrees": 1,
  "dwellMilliseconds": 100,
  "invertDispense": false,
  "preGcode": "",
  "postGcode": ""
}
```

Replace every coordinate with measurements; this is a schema illustration, not a runnable machine job. Board-frame points additionally need `calX/calY`.

## Status and provenance

- [Video review status](docs/VIDEO_NOTES.md): metadata verified, spoken content unavailable; no transcript fabricated.
- [Commissioning record](docs/COMMISSIONING.md): physical tests remain pending.
- Upstream remote is retained as `upstream`; local branch is `automation/bootstrap`.
- GitHub fork: [theinstancelabs/paste-automation](https://github.com/theinstancelabs/paste-automation), created through the authorized `aabdel0181` session.
- Original project handoff: `../lumenpnp-handoff/PROJECT_HANDOFF.md` and `../PHASE_1.md`. Their registration, clearance and two-air-run gates carry forward here.

## License

MPL-2.0, retained in [LICENSE](LICENSE). Original software by its upstream contributors; changes in this fork are under the same license. Upstream logos, product branding and deployment-domain files have been removed from the derivative UI. Third-party names in documentation identify source projects and compatible hardware, not endorsement. Hardware and external examples have their own licenses, described in the research notes.

## User-confirmed target (2026-09-25)

LumenPnP v4.1 with the latest official extruder, installed on nozzle 2. This identifies the machine family; installed firmware, current, exact extruder revision and all measured clearances remain to be recorded. Requested GitHub owner is InstanceLabs; the existing handoff uses the `theinstancelabs` organization. Preferred contributor is `aabdel0181`, with another authorized account acceptable.
