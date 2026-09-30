# Video source and review status

Requested source: [LumenPnP Paste Extruder BETA Kit Setup Instructions](https://www.youtube.com/watch?v=N_p62_QUoKI), by Opulo.

Verified from YouTube page metadata on 2026-09-25:

- Published December 3, 2024.
- Duration 19 minutes 40 seconds.
- Description links the [extruder hardware repository](https://github.com/opulo-inc/paste-extruder) and [Leash Python API](https://github.com/opulo-inc/leash).
- An English auto-generated caption track is advertised.
- A corrections card is present, but its correction text was not returned in the inspected metadata.

## Historical access status: incomplete on 2026-09-25

The web fetch failed, but a direct read of the public YouTube page exposed the metadata above. Requests to the advertised caption endpoint in JSON3, XML/SRV3, and default format each returned HTTP 200 with an empty body. No usable audio or spoken transcript was obtained. No chapter timestamps were available in the inspected response.

Consequently this file contains **no invented transcript, quotations, chapter timings, or claims that the video was watched**. A full verbatim transcript of a linked third-party video is not reproduced here. Once source content is available, this document can be extended with timestamped paraphrased engineering notes, including any corrections.

## Verified current documentation, not video narration

The hardware README confirms right-toolhead installation and the mirrored base/clamp requirement. Its Python example controls B rotation through Leash. The current browser utility offers a newer documented Gerber/camera workflow; the video's description does not link that utility. Do not treat the current web instructions as a transcription of the 2024 video.

For immediate installation and implementation decisions, consult [HARDWARE_FIRMWARE.md](HARDWARE_FIRMWARE.md), which distinguishes repository evidence from unverified machine settings. The remaining video-specific work is to review the mechanical installation sequence, syringe loading, commissioning demonstrations, and corrections against accessible source content before assigning timestamps or attributing instructions to the speaker.


## User-supplied transcript reviewed — 2026-09-30

The user supplied a timestamped transcript spanning 00:00:03–00:19:57 in this project conversation. The spoken-content summary below is grounded in that supplied text, not in successfully downloaded captions or an audiovisual viewing. Automated network retries still returned empty caption bodies. The earlier access limitation is now resolved for this supplied spoken text; visual assembly details and the separate correction-card text remain unverified. Its timestamps overlap and its ending differs from the earlier metadata duration, so treat timing as approximate. Several transcribed commands/names are garbled; do not execute them literally.

| Supplied time | Spoken content reviewed | Implication for this integration |
| --- | --- | --- |
| 00:00–01:59 | Beta kit contents can change; demonstrated kit has syringe assemblies, Luer-lock tips, printed mount/clamp, NEMA11 motor and connector adapter. The speaker thinks the supplied tips are 20 gauge. | Record the actual installed revision, syringe, tip and motor rating; the narration is not a parts inspection of this user's kit. |
| 02:00–04:38 | Remove both USB and barrel-jack power before unplugging motors. Remove the right pneumatic head, retaining its assembly/screws, and reuse the right motor cable. V4 is demonstrated. | Installation is user-confirmed complete. Keep original head for reversible restoration; do not infer wiring inspection from software state. |
| 04:38–06:52 | Align the mount upright/perpendicular, check Z travel, install motor and check gear rotation/clearance before clamping the syringe. | Still measure coupled both-head clearance and cable sweep on this installation. |
| 06:22–08:40 | Filling through a Luer-lock adapter can reduce introduced air; removing/reinserting the plunger introduces air and complicates clean extrusion. The example design uses a 3 ml syringe and an M3 threaded rod. | Record syringe/material/loading method; trapped air is a commissioning variable, not a software dose error by default. |
| 08:14–10:38 | Seat syringe thumb grips, adjust threaded assembly to engage, fit the clamp without looseness, attach tip, reuse the motor connector, and route the unused tubing/cable clear. | Confirm seating, free gear engagement and cable clearance before motion. No photo-based installation inspection has yet been performed. |
| 10:43–12:39 | Demonstrates a browser debug tool/Web Serial and identifies the motor as Marlin B; demonstrates homing. | These are alternative control methods. Preserve OpenPnP as the sole owner; do not open Web Serial or Leash alongside it, and do not copy the demonstrated home sequence blindly. |
| 12:08–13:41 | Describes 200 mA default A/B current, a 400 mA example, and short higher-current experiments. Readout labels I/J differ from command axes A/B; demonstrates no-parameter M906 readout and B-addressed current changes. | Query actual current first. Do not issue B400 or higher-current changes from this video alone; actual motor/driver rating and temperature/stall evidence are required. |
| 13:09–15:11 | Discusses absolute G90 versus relative G91; repeats of absolute targets differ from relative increments. Demonstrated negative B extrudes and positive B retracts. Raw Z20 is described as up and Z50 as down in that setup. | Verify this machine's actual direction/units. G91 affects XYZ too. Neither those raw Z examples nor raw B examples are OpenPnP N2 calibration; no raw mode/coordinate changes are sent by the air adapter. |
| 15:06–17:50 | Leash example uses hardcoded pad positions, homes, sets current, resets B origin, primes, waits after controller work, then moves through pad coordinates. | Do not run unchanged. Retain pure planning, native tracking, measured coordinates and actual completed-motion checkpoints. Python wall-clock sleep alone does not prove queued motion is complete. |
| 17:25–19:22 | Shows a small per-pad B dose, an end park, and recommends pinning Leash because its API changes. | Example dose/park are not calibrated here. Fork is pinned; no automatic end park or separate Leash controller is introduced. |

This review adds evidence for B-axis use, current-readout naming, syringe seating/loading and position-mode hazards. It does not validate firmware on the installed machine, actual current, direction, safe Z, paste flow, or the video correction card. Physical air/coupon tests remain pending.
