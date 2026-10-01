# Fresh FTP registration review from camera fiducials

`fresh_ftp_registration.py` is an offline calculator for a newly measured FTP board. It fits the board-to-machine XY similarity transform from the visually centered top-camera measurements of FID1 and FID2, then checks that transform against an independently measured FID3. On pass, it writes repeatable candidate machine XY coordinates for all 80 resistor paste-pad centers. It does not open OpenPnP, move the machine, modify a job, apply a board transform, or infer paste availability, Z, nozzle offsets, clearance, dose, or calibration.

The only design source accepted is `pnp/pcb/ftp/ftp.kicad_pcb`. Its fiducials and resistor paste-pad centers are transformed into the positive-Y front-board frame (`x = KiCad X`, `y = -KiCad Y`), matching the existing Gerber geometry convention. The saved `ftp-20260924.job.xml` and its board transform/placed flags are deliberately not inputs.

To use it, create three fresh, independently verified single-axis XY camera-survey records in the same OpenPnP JVM and configuration, with unchanged raw Z/A/B and top-camera Z/rotation. At each point, center the actual identified copper fiducial under the Top camera and capture its raw image. Review the identity and center in each image. Use the input template below, with each report's SHA-256 and the SHA-256 of the `afterImages.top` PNG. `fiducialIdentityReviewed` and `centeredInTopImageReviewed` must be set only after human image review. The tool independently checks the image component across red-channel thresholds and rejects a center error above two pixels. Reports must be less than 30 minutes old.

```json
{
  "schema": 1,
  "scope": "fresh-ftp-top-camera-fiducials",
  "operator": "reviewer name",
  "board": "/home/lumen/lumenpnp/pnp/pcb/ftp/ftp.kicad_pcb",
  "roi": [500, 350, 850, 700],
  "thresholds": [80, 100, 120, 140],
  "measurements": {
    "FID1": {
      "report": "/absolute/path/to/FID1/report.json",
      "reportSha256": "64 lowercase hex characters",
      "topImageSha256": "64 lowercase hex characters",
      "fiducialIdentityReviewed": true,
      "centeredInTopImageReviewed": true
    },
    "FID2": { "report": "...", "reportSha256": "...", "topImageSha256": "...", "fiducialIdentityReviewed": true, "centeredInTopImageReviewed": true },
    "FID3": { "report": "...", "reportSha256": "...", "topImageSha256": "...", "fiducialIdentityReviewed": true, "centeredInTopImageReviewed": true }
  }
}
```

Run from the repository root, choosing a new private output path:

```sh
python3 automation/paste/analysis/fresh_ftp_registration.py \
  /absolute/path/to/fresh-registration-request.json \
  /absolute/path/to/private-fresh-registration-review.json
```

Acceptance is fail-closed: the FID1/FID2 similarity scale must be 0.99–1.01, the held-out FID3 camera-center residual must be at most 0.08 mm, and every reviewed red fiducial must be unambiguous, unclipped and within two pixels of the top-image center. All three surveys must be successful, same-JVM/configuration, same raw Z/A/B and same top-camera imaging plane. Report and image hashes bind the reviewed inputs. The output contains every R1–R40 pad target in design and machine XY, but remains `executionReady: false`; it is only a fresh transform candidate for separate review and job preparation.

Checks: `python3 -m unittest discover -s automation/paste/analysis -p 'test_fresh_ftp_registration.py'`. Tests use synthetic reports and images and never connect to a machine.

## Optional three-fiducial affine model

Set `registrationModel: "three-fiducial-affine"` explicitly to fit all three fiducials. This preserves orientation and requires both singular values in 0.99–1.01 and axis skew no greater than 0.3 degrees. FID3 is a fitted point in this model, never an independent residual check. Without held-out pad evidence, the result has candidate scope and `acceptance.passed: false`; native FTP preparation rejects it. The default similarity model and its independent FID3 limit remain unchanged.

Acceptance additionally requires `imageJacobianEvidence: {path, sha256}` and exactly three `heldOutPadChecks`, for R1.2, R16.1 and R40.1. Each check supplies `padId`, `report` (absolute path), `reportSha256`, `topImageSha256`, `observedCenterPixel: [u,v]`, `padIdentityReviewed: true` and `centerMeasurementReviewed: true`. These explicit reviews must follow inspection of the actual identified pad images. Each pad must be within 8 pixels of image center and its measured machine coordinate within 0.08 mm of the affine prediction. The three pad reports must be distinct from one another and from the three fitted fiducial reports.

The Jacobian JSON uses schema 1, scope `measured-top-camera-image-jacobian`, `pixelShiftPerCameraMm` (a 2×2 matrix), `session: {jvmStartMs, liveConfigurationSha256}`, `fixedRawZAB`, named `reviewedBy`, integer `reviewedMs`, and three `sourceMeasurements`. Each measurement binds `report: {path,sha256}`, `image: {path,sha256}`, `rawXY`, and the measured `centerPixels`. The calculator recomputes the Jacobian from these report/image measurements. Pad coordinates use camera XY minus the inverse Jacobian applied to the observed pixel displacement. Reports/images must share the registration imaging plane and session, and remain within the existing 30-minute offline freshness limit.

The accepted affine scope is `offline-fresh-ftp-three-fiducial-affine-with-held-out-pad-checks`. Both native preview and runtime re-hash its source reports/images, recompute the affine bounds, Jacobian and held-out residuals, and require the target record's three `padChecks` to bind those same held-out reports/images. Existing CAD, provisional tip/Z evidence, freshness, exact two-pad scope, ledger and motion gates still apply. This establishes an XY registration model only; `executionReady` remains false and no physical paste qualification is implied.
