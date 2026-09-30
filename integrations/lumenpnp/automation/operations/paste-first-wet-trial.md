# First bounded physical priming trial — 2026-09-30

Fifteen native B-only increments of−20° completed, moving B720→420 at rawX295,Y310,Z31.5,A720. Each controller position/count check passed; XYZ/A remained fixed. Current remained200mA. Pump remained off. The needle was over the blue scrap behind the FTP board with a deliberately large noncontact gap.

No paste emerging or deposited was confirmed in the USB images. The17.54µL nominal CAD displacement is not delivered paste. This is verified controller operation, not flow calibration or successful deposition. The close view requested from the user must resolve gear/plunger/outlet behavior before further priming or force changes. Preserve the300° charged ledger; never reset or replay it. No resistor pads were pasted.

The actual native formatter included the harmless literal `; move to target` suffix. Its exact form is now accepted while arbitrary suffixes remain rejected;12 policy tests passed. The single-increment continuation helper waits for terminal evidence and requires a newly reviewed image for each next increment. Its poll now tolerates an incomplete JSON read during a report write; it never resubmits the action.

## Additional pulse and new camera, 2026-09-30

User confirmed no paste at needle and requested additional extrusion followed by top-camera inspection. One explicitly amended 20-degree pulse completed: B420 to400; cumulative320 degrees, all prior300 retained. Terminal report3d2fa2ea-79d7-490a-bfd1-f9bda02f4d46 verified controller counts with XYZ/A unchanged. Current remains200mA. New4000x3000 USB before/after images show no visible paste at outlet.

Completed constant-Z camera route to rawX340,Y246,Z31.5,A720,B400 (route283c121a-0182-423c-9d0e-9eb8b9606042). Top exposure bracket1790797594236 restored settings; comparison with pre-prime image shows no obvious new deposit. Scrap surface is out of focus, so absence of a tiny deposit cannot be established. No successful dispensing or flow calibration claimed.

Web viewer now uses Galyimage stable USB identity with1920x1080 MJPG preview. Local and existing authenticated external frame endpoint verified. OpenPnP top/bottom camera and serial ownership unchanged.

## Gear observation and completion-timeout diagnosis

A recorded20degree B400to380 diagnostic established visible drive-gear rotation; outlet remained bare. User then explicitly requested sustained priming until paste emerges. A100degree B380to280 pulse encountered the native10second M400 timeout despite the physical move requiring approximately25seconds. No replay was sent. Exact read-only audit of faultba7bf3db-7458-47e4-9e80-d9f90df6ac89 received late completion ACK and fresh M114 showing B280 count1243, with all XYZ/A unchanged. The440degree total stays charged. Original fault report remains immutable.

Runtime100degree pulses now temporarily use a finite60second driver timeout, restored to the original10seconds in finally; no saved configuration change. Fresh visual observations and explicit ledger-bound amendments remain required between pulses.

User requested300degrees followed by12seconds of dwell. First fast300degree pulse b2e50a99-cec7-46c7-9204-42974a7fa6d5 completed with verified controller counts at cumulative2240degrees, rawB-1520; XYZ remained fixed. Speed20degrees/second and current200mA. The wrapper waited12seconds after verified native completion before image capture; no paste output was visible. Physical flow remains uncalibrated.

User reported that manual plunger pressure extrudes paste and explicitly requested continuous gear-driven priming while watching. Manual displacement is unknown and invalidates precision calibration; commanded displacement history is retained without treating manual output as zero. Supervised mode uses one300degree pulse at a time, without the12second dwell. It checks an external stop file and a parent-maintained heartbeat no older than60seconds before each physical dispatch. A stop finishes the current pulse before preventing the next; it does not replay or reset charged history. No automated image acceptance is claimed in this mode.
