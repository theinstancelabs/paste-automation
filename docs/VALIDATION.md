# Validation record — 2026-09-25

Software checks performed on macOS with Node 24.19:

- Node test suite exercises Gerber modal coordinates/units, malformed imports, duplicate reload prevention, noncollinear registration, strict planner validation, machine-vs-board coordinates, dry-run absence of B movement, wet-cycle cancellation at clearance, serial ACK fragmentation/races, disconnect/error/timeout and reconnect.
- Vite production build succeeds.
- `npm audit`: zero known vulnerabilities after removing unused browser/polyfill dependencies and updating Vite.
- Safari UI smoke check: app loads without OpenCV, Air run is selected by default, legacy motion controls are disabled, and Preview with no profile reports “job and profile are required.” Safari was used for offline UI inspection only; Web Serial requires a supported browser on the machine computer.
- Independent subagent review found and prompted correction of unsafe intermediate pause checkpoints, stale coordinate selection, camera-dependent reconnect, and controller reset handling.

No physical machine connection, flash, homing, movement, extrusion, camera registration or production-board verification was performed. The suite does not establish physical calibration, serial timing on the actual controller, or successful operation on v4.1 hardware. GitHub Actions is configured to repeat tests/build; its remote execution status must be checked separately.
