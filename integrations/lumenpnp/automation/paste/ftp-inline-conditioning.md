# Continuous scrap conditioning and one FTP pair

The optional `contiguous-native-ftp-conditioned-two-pad` scope (and `-preview` counterpart) executes one reviewed scrap preparation, clearance-only transfer, and one compensated pair in a single existing native task. It retains the 40-stage ceiling, signed-B amounts and speed, full-speed bounded XYZ steps, detached exact formatter preview, one whole-gross ledger reservation, per-stage counts/position verification, stop handling and no replay. This scope does not authorize a larger pad group or establish physical dispensing quality.

The existing FTP target record adds `inlineConditioning`:

```json
{
  "schema": 1,
  "protocol": "scrap-condition-transit-two-pad",
  "experiment": "exact parsed authored transfer-preparation experiment object",
  "experimentEvidence": {"path": "/absolute/experiment.json", "sha256": "..."},
  "maximumTransferMilliseconds": 15000,
  "prefixStageCount": 12,
  "retractionStageIndex": 10,
  "liftStageIndex": 11
}
```

Indices above are illustrative and must match the computed prefix. The policy reconstructs that prefix from the explicit experiment: prime 40/60 in -20 stages, reviewed pre-wipe relief, exactly one named noncontact wipe no longer than 2 mm, lift, one dummy point, explicit -6 or -20 conditioning dose, selected retraction and declared wait, then lift without idle relief. The experiment, complete path review and provisional scrap profile are hash-bound; `profile.measurementEvidence` must identify the complete path review, whose `experimentEvidence` identifies this experiment. Prefix XY may use its separately reviewed scrap clearance; every subsequent XY stage must use the common FTP transit clearance. Scrap and board gap evidence remain distinct.

`compensatedSequence` retains the ordinary two-pad dose/retract/wait/final-idle fields and exact stage indices. It must omit the external completed-conditioning report/ledger, preparation/tip-observation evidence and historical conditioning-time fields: conditioning now happens and is verified inside this same request. Immediately before the first FTP restore, runtime checks the actual completed prefix and retraction wait. More than 15 seconds since its verified retraction rejects the restore and faults the reservation without refund or automatic replay. The deadline includes the declared retraction wait, lift and transit. No image capture or artifact preparation occurs between the prefix and pair.

The offline generic preparer selects this scope only for `targetSurface: "scrap-conditioned-ftp-demo"`; ordinary scrap and two-pad defaults remain unchanged. The route still requires an explicit authored target record for exactly two unique pads on one resistor, current physical clearance/availability review and successful complete offline validation before detached preview.

## Revalidate an unchanged registration without refitting

An optional target `registrationRevalidationEvidence` identifies a schema-1 `ftp-registration-revalidation` record. It binds `originalRegistrationEvidence` to the unchanged accepted registration bytes, names `reviewedBy`/`reviewedMs`, explicitly states `boardUnmovedSinceRegistration: true`, and supplies exactly `measurements.FID1`, `FID2`, `FID3`. Each measurement binds report/image `{path,sha256}` pairs and explicitly supplies `fiducialIdentityReviewed: true`, `centeredInTopImageReviewed: true`, `observedCenterPixel` and `imageSizePixels`.

The three successful new survey reports must be distinct from one another and from the old fitted observations. Their sources may be at most 15 minutes old at the authored revalidation review. That immutable revalidation remains valid for one hour, matching the original registration window; every later wet target, path review and current image still has its separate five-minute freshness gate. The parent explicitly chose this lifetime after fresh three-fiducial agreement and successful R39 transfer, to avoid redundant full camera surveys of the unchanged fixture between bounded trials. No timestamps are refreshed. Every new center must be within 2 pixels, and every camera position within 0.08 mm of the unchanged original transform prediction. Session, configuration, raw Z/A and top-camera plane remain identical; the three new sources must also share their own current B, while the original registration/Jacobian retain their historical B values.

Only a passing explicit revalidation permits consuming the historical registration and its original independently checked images beyond their ordinary one-hour window. Original timestamps are never refreshed, and all historical report/image hashes, affine fit bounds, measured Jacobian and held-out residuals are still verified. Without this record the original one-hour gate remains. This verifies continued XY registration only; it does not refresh a pressure state or qualify Z, deposited volume or reflow.

The selected `conditioningDoseDegrees` is part of the immutable experiment and exact reconstructed prefix. Authoring defaults it to 20; explicit 6 changes only that existing B stage, with no additional stages or change to the FTP pad doses. The historical external-tail protocol remains unchanged.

Optional `conditioningFinalWipeMm` is 0 (default) or exactly 1.5. The latter requires conditioner6, retract3 with500 ms wait, and explicit `attestations.conditioningFinalWipeReviewed: true` in the author input/full-route review. The hash-bound experiment carries that review flag. After the dummy retraction wait, exactly one +X1.5 mm move at the scrap working Z holds B unchanged, then the existing five-mm lift follows. No other low XY is admitted. The reviewer must inspect the entire fresh scrap wipe path. Gross/net B accounting is unchanged; the prefix gains one stage and the complete route must still fit its existing scope cap.

The 15-second transfer deadline still starts at verified retraction and includes its wait, the final wipe, lift and transit. A stop before the wipe holds position instead of performing low XY; a stop after the wipe permits only the next already-reviewed clearance lift. No automatic recovery movement is introduced.
