# Reviewed no-B scrap wipe request author

`author-no-b-scrap-wipe.py` packages an explicitly reviewed noncontact wipe on bare scrap into the existing disabled contiguous-air preparation flow. It has no OpenPnP, controller, bridge, camera, vacuum, or dispatch connection. It never changes B or creates an FTP target. It writes an offline `preview-request.json`; preview and any later execution remain separate actions.

Run it with a JSON input document and a new output directory:

```sh
python3 automation/paste/author-no-b-scrap-wipe.py --inputs reviewed-input.json --output automation/evidence/<new-run>/
```

The input uses schema `1`, scope `reviewed-no-b-scrap-wipe-inputs`, and contains `reviewedBy`, integer `reviewedMs`, explicit `reviewBasis` and `profileBasis`, exact fresh `startRaw` from the barrier, and hash evidence under `sources` for exactly `template`, `barrier`, `image`, `profileBase`, `previousReport`, and `ledger`. Every `attestations` entry must be explicitly `true`: `scrapOnly`, `bareScrapReviewed`, `bothHeadsClearanceReviewed`, `tipAndWipeReviewed`, `noBNoVacuumOrHoming`, and `noFtpTargets`.

The `wipe` object has exactly six fields: `axis` (`X` or `Y`), nonzero `deltaMm` with magnitude at most 2 mm, `workRawZ`, `clearanceRawZ`, `estimatedGapMm`, and `gapUncertaintyMm`. Start Z must equal clearance Z; work Z must be above it by at most 5 mm. Z endpoints, wipe endpoint and start coordinates must lie on the 0.01 mm reporting grid. The gap interval must have a lower bound of at least 0.1 mm. The explicit gap describes the wipe at work height. The derived provisional profile is anchored at clearance height and adds the work-to-clearance Z difference; the wipe stage retains the authored work-height gap. The generated route is Z to work height, one reviewed X/Y wipe at that height, then immediate Z lift back to clearance. The author rechecks all source hashes after the existing generic validator has written the disabled request.

There is no separate tip-image source field. `tipAndWipeReviewed` is the reviewer’s explicit physical judgment, not an automated tip check or a separate hash-bound tip photograph. Retain any additional tip evidence with the trial; the attestation does not establish later tip condition.

Use a new exclusive output directory for each preparation. The helper refuses stale or mismatched hashes, an incomplete barrier, unreviewed inputs, a changed start pose, invalid gap or travel bounds, reused output directories, and any supplied FTP target field. The generated route is a preparation artifact; it does not establish physical removal or a clean tip.
