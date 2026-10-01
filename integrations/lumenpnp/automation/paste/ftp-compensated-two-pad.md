# Optional compensated FTP pair

This is a bounded alternative within the existing FTP two-pad scope. Omitting `compensatedSequence` preserves the legacy two-negative-dose-only policy. The compensated option is wet-only; use the existing unmodified air record for an air route. It does not qualify paste volume, pressure, physical transfer or a complete board process.

Keep the existing target record's two unique pads of one resistor, three distant pad checks, current three-fiducial registration, availability review, provisional offset/surface evidence, 0.01 mm coordinates, and machine/session/configuration identities. Each pad replaces legacy `doseStageIndex` with:

- `restoreStageIndex`: one -R B stage at the pad.
- `doseStageIndices`: one stage for dose2/3/4/6/20, or exactly two consecutive -6 stages for dose12.
- `retractStageIndex`: one +R immediately after the last dose.
- `liftStageIndex`: the immediately following Z stage to common clearance.

Restore, complete dose, retract and lift are consecutive within each pad group; pad groups execute in record order. Restore waits remain zero. Optional `retractDwellMilliseconds` selects 0, 200 or 500 ms after each +R and before the next lift; omission preserves zero. The chosen dose wait applies only to the last dose stage. All B stages must belong to these groups or the explicitly indexed final idle relief. Low XY moves and wipes remain forbidden on FTP, and the existing full XY/Z speed, B speed, formatter, count, N2, raw/head bounds and gross-ledger checks remain active.

The target record's optional object has this structure (all evidence uses absolute `path` plus SHA-256):

```json
{
  "compensatedSequence": {
    "schema": 1,
    "protocol": "restore-dose-retract-lift-two-pad",
    "doseDegrees": 4,
    "retractDegrees": 2,
    "dwellMilliseconds": 200,
    "retractDwellMilliseconds": 0,
    "idleReliefDegrees": 20,
    "finalIdleStageIndex": 13,
    "conditioningFinishedMs": 0,
    "maximumElapsedMilliseconds": 120000,
    "conditioningReportEvidence": {"path": "/authored/report.json", "sha256": "<hash>"},
    "conditioningLedgerEvidence": {"path": "/immutable/ledger-copy.json", "sha256": "<hash>"},
    "preparationExperimentEvidence": {"path": "/authored/experiment.json", "sha256": "<hash>"},
    "tipObservationEvidence": {"path": "/authored/tip-review.json", "sha256": "<hash>"}
  }
}
```

This is a schema illustration, not a runnable request. Derive indices from the actual stages and `conditioningFinishedMs` from the actual verified final retraction stage timestamp in the report (before lift and image capture). Dose is limited to 2/3/4/6/12/20 and R to 2/3/4/6; dwell is an integer 0..2000 ms. Optional `idleReliefDegrees` is 20 or 40, default 20. At 20, retain `finalIdleStageIndex` and one +20 stage with a 2000 ms wait. At 40, omit that singular field and provide `finalIdleStageIndices: [i, i+1]` for exactly two +20 stages, with zero wait on the first and 2000 ms on the last. The consecutive idle stages immediately follow the second lift and end the route; mixed singular/plural mappings are rejected. Its gap metadata is the board profile gap plus the clearance-height difference. Both restores and all dose/retract stages use the same reviewed pad pose and board gap evidence. FTP gross is `2*doseDegrees + 4*retractDegrees + idleReliefDegrees`; final B is initial B minus both doses plus selected idle relief. For dose 4 / R2 / final 40 the pair charges 56 gross degrees and ends 32 degrees above entry B; every restore, retract and idle stage remains charged, including reserved stages on a fault.

Preparation must be a completed same-session scrap batch whose actual fully verified history ends with exactly -20 conditioning dose, selected +R, its declared retraction wait, then lift. No idle relief may follow. Its hash-bound original clearance review must reference the explicit `mode: "transfer-preparation"` experiment and the same R and maximum elapsed limit. Its actual conditioning wait must equal the experiment’s `conditioningDwellMilliseconds`, falling back to `dwellMilliseconds` and then 2000. The preparation experiment and actual retraction stage must also match the target record’s `retractDwellMilliseconds` (default zero). For a nonzero wait, the completed stage record must confirm the requested wait, at least that elapsed duration, no observed stop, and an end timestamp between verified retraction and report completion. The tip observation must be captured after that completed report. The entry-age clock still starts at verified retraction, so time spent waiting is included conservatively. The actual completed report must be the request's `previousReportEvidence`; its ledger hash must equal the current previous-ledger hash, with selected +R as the verified tail and unchanged terminal B. Use an immutable ledger copy for `conditioningLedgerEvidence`, because runtime deliberately replaces the live ledger when reserving this new batch.

The authored tip observation requires `reviewedBy`, integer `capturedMs` and `reviewedMs`, `noLongStrand: true`, `conditioningReportEvidence` matching the exact report, and `imageEvidence`. Capture must follow conditioning completion and precede review; review must precede the FTP target review. These are explicit human/agent observations, never generated attestations. The elapsed limit must be chosen and reviewed, be 1..300000 ms, and match the preparation experiment. It is checked during validation and again immediately before first restore, with all conditioning sources rehashed. A timeout does not authorize a restore or release any reserved gross. Once entered, ordered runtime verification and existing stop/lift behavior apply.

This establishes a bounded motor-history entry state, not measured pressure. If conditioning or observation is stale, the ledger changes, an intervening B move occurs, or the tip develops a strand, prepare and review again on scrap. Do not recover the extra20 from a normal coupon over the FTP board.
