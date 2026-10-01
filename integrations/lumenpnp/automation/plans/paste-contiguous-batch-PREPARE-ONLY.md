# Contiguous scrap batch request — preparation only

The two new scripts read `automation/plans/paste-contiguous-batch-preview-request.json` and `automation/plans/paste-contiguous-batch-request.json`. Neither file is created here. The parent reviewed and enabled the runtime source and registered the two bridge actions; this document itself creates no request and dispatches no action. Prepare new requests only from a fresh same-JVM position barrier, current model snapshots, a current reviewed image, and current ledger/report evidence. Do not copy coordinates from an old cycle.

Both requests use `schema: 1`, `enabled: false`, the same UUID `id`, `sessionId`, `jvmStartMs`, `createdMs`, `imageCapturedMs`, `reviewedImageMs`, `liveConfigurationSha256`, `expectedRaw`, `expectedDriver`, `expectedNativePoses`, `stopPath` (absolute, absent before starting), and `mode: "air"` or `"wet"`. The scopes are `contiguous-native-scrap-batch-preview` and `contiguous-native-scrap-batch`. Supply `rawBounds` as `{X:{min,max},Y:{min,max},Z:{min,max},B:{min,max}}`, `headClearanceBounds` as `{N1:{minX,maxX,minY,maxY,minZ,maxZ},N2:{minX,maxX,minY,maxY,minZ,maxZ}}`, `bothHeadsClearanceReview: true`, `clearanceReviewEvidence:{path,sha256}`, `xyClearanceRawZ`, `receivingProfile`, `previewStages`, and `finalTargetRaw` in both.

`receivingProfile` must state `provenance: "commissioning-provisional"`, `precisionCalibrated: false`, `flowCalibrated: false`, `sha256`, `estimatedGapMm`, `gapUncertaintyMm`, a specific `basis`, and `rawPose` for the current XYZ/A pose. The lower gap bound must be at least 0.1 mm. This does not claim hard contact or precision calibration. Every wet B stage also needs its own `gapEvidence:{path,sha256}`, `estimatedGapMm`, and `gapUncertaintyMm` with the same conservative lower bound.

`previewStages` has 1–40 contiguous one-axis entries. Each preview-request entry is `{axis,startRaw,targetRaw,speedFraction}` plus any B gap fields or wipe fields. Raw `A` is fixed throughout. X/Y/Z use speed 1; B uses 0.05. Each X/Y move is at most 10 mm, each Z move at most 5 mm, and B deltas are only ±2, ±4, ±6, or ±20 degrees. XY moves require `startRaw.Z === xyClearanceRawZ`; an intentional dispense-height wipe instead needs `wipeReview: true`, `wipeReviewEvidence:{path,sha256}`, and stage estimated gap/uncertainty with at least 0.1 mm lower bound. Air mode has no B stages. Wet mode has at least one B stage.

A B stage may include `dwellMilliseconds` as an integer from 0 to 2000; omission means zero. No other axis may specify dwell. The runtime records the requested and elapsed wait only after fresh position/count verification and the corresponding B ledger write. It waits without sending commands and checks the cooperative stop file at least every 50 ms. The detached preview and final request bind the exact dwell value.

The `stopPath` is a cooperative operator stop file. If it appears at an inter-stage boundary, the batch faults remaining reserved B budget and never resumes automatically. If the current pose is below the reviewed XY clearance Z, the only motion permitted after a stop is an already-listed Z stage whose target is exactly that clearance; there is no synthesized lift. The report records whether the stop occurred at clearance.

The detached preview writes one formatter JSON per stage and a report. Copy each generated stage’s exact `expandedCommands`, `path`, and `sha256` into the physical request; keep all stage poses, bounds, gap/wipe evidence, and profile identical to the preview request. The physical request also retains the existing cycle evidence fields: `barrierEvidence`, `profileEvidence`, `primeLedgerEvidence`, `priorLedgerEvidence`, `carryoverEvidence`, `nativePreviewEvidence`, `reviewedImageEvidence`, `previousReportEvidence`, `previousLedgerSha256`, `primeLedgerSha256`, `carryoverSha256`, `syringeId`, `budgetAmendmentEvidence`, and `evidence` (all hash-bound). Wet mode reserves the whole B gross budget before the first query and consumes all reserved gross on fault. Air mode reads and verifies the ledger hash without changing it.


## Explicit FTP demo two-pad extension

The existing scrap scopes remain unchanged. A cleaned FTP demo board must use
`contiguous-native-ftp-two-pad-preview` and `contiguous-native-ftp-two-pad`.
This is bounded commissioning, not production acceptance or a calibrated recipe.
The same native owner, stage formatter, speed/step limits, B ledger reservation,
stop behavior, and no-replay checks apply. Cleanup/priming on scrap stays separate.

An offline recipe selects `targetSurface: "cleaned-ftp-demo"` and supplies
`ftpTargetEvidence: {path, sha256}` for an explicitly authored JSON record. The
existing prepare helper loads that record into `ftpTargetRecord`; preview and
runtime compare it exactly and independently verify the source file hashes. The
helper does not invent review attestations or select an offset, Z, gap or dose.
The record must contain:

- `schema: 1`, `scope: "ftp-two-pad-commissioning-targets"`, a concrete `boardId`,
  and matching `sessionId`, `jvmStartMs`, `liveConfigurationSha256`.
- A named `reviewedBy` and integer `reviewedMs` no more than five minutes old;
  explicit `boardCleaned: true`, `padsAvailable: true`, and
  `boardUnmovedSinceRegistration: true`.
- `provenance: "commissioning-provisional"`, `precisionCalibrated: false`,
  `flowCalibrated: false`; never promote image estimates to calibrated geometry.
- Hash-bound `cadEvidence`, `registrationEvidence`, `tipOffsetEvidence`,
  `surfaceEvidence`, and `padAvailabilityImage` (absolute `path` and `sha256`).
- `cameraMinusTipXYMm: [x, y]`, explicitly chosen by the reviewer, and
  `surface: {rawZ, estimatedGapMm, gapUncertaintyMm}` for this board. The positive
  gap lower bound remains at least 0.1 mm; the entire route must stay at or above
  that reviewed dispense height in physical space (raw Z no greater than rawZ).
- Exactly three `padChecks`, identified by `reference` R1, R16 and R40. Each has
  `padId`, `reviewedAligned: true`, `reportEvidence`, and `imageEvidence`.
- Exactly two `pads`, each `{padId, rawPose: {X,Y,Z,A}, doseStageIndex}`. IDs must
  be the two distinct pads of one resistor. For wet mode each index points to
  its single negative-B stage. For air mode both indices are `null` and no B
  stage is permitted.

The registration must be the accepted three-fiducial FTP record, bind the same
CAD/session/configuration, and contain its 80 camera pad targets. Its three
fiducial reports/images and the distant-pad reports/images are hash-verified;
reports must be successful and reviewed within one hour. Distant camera checks
must be within 0.1 mm of the registered pad center. The two raw head targets must
match registered camera XY minus the explicitly selected offset within 0.001 mm
(rounding allowance only). Their Z/A and negative-B stage poses match exactly.
Exactly two total B stages, both negative and assigned one per pad, are accepted
on wet FTP. Positive B relief is also excluded from this branch; perform
cleanup separately on scrap. No dispense-height XY/wipe is accepted on FTP.

`tipOffsetEvidence` and `surfaceEvidence` are explicitly authored selection
records. Both carry `boardId`, `jvmStartMs`, `liveConfigurationSha256`,
`reviewedBy`, `provenance: "commissioning-provisional"`,
`precisionCalibrated: false`, and hash-bound `basisEvidence`. The tip selection
record carries the exact `cameraMinusTipXYMm`; the surface selection carries the
exact `surface` object. For example, the existing provisional offset calculation
may be the tip selection's `basisEvidence`; it is not silently rewritten or
promoted to a machine setting. Source hashes are rechecked before task preflight.

No physical FTP result follows from this extension or its offline tests. The
parent must review the explicit two-pad record and detached preview before the
first wet demo-board trial, then inspect both deposits before further work.
