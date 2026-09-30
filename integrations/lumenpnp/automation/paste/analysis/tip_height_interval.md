# Same-world-XY endpoint height interval

`tip_height_interval.py` processes existing evidence only. It neither captures images nor commands the machine, and it does not update offsets or authorize motion. Choose each physical nozzle/needle endpoint manually; the helper never infers identity from a highlight or the largest object.

Use a fixed, stable HD side camera with unchanged lighting. Camera movement invalidates the sequence. Independently center the actual N1 tip and actual needle endpoint at the same bottom-camera point; saved N1 offset from another A rotation is not sufficient. Save distinct, reviewed bottom images for both alignments. Bottom camera focus and saved camera Z are not an absolute tip datum.

Collect at least two distinct stationary side frames per pose:

- `n1Reference`: N1 at the reviewed reference height.
- `n1Dither`: same raw XY/A/B with a separately authorized positive raw-Z dither of at most 1 mm.
- `n1Return`: return to precisely the reference raw Z, to include repeat jitter.
- `rightLow` and `rightHigh`: actual needle centered at the same world XY, with separately reviewed raw-Z samples that bracket the N1 endpoint row. These two poses retain the same raw XY/A/B. The helper does not execute these poses.

The input JSON has `schema: 1` and `scope: "same-world-XY-side-endpoint-height-interval"`. Supply `operator`, `cameraSetupId`, `sameWorldXYReview`, `n1DatumReview`, and `localLinearityReview` text. Set `fixedCameraAndLightingReviewed`, `sameWorldXYReviewed`, `stationaryCapturesReviewed`, and `endpointIdentityReviewed` only after actual review. Supply numerical `referenceN1HeightMm`, `coupledZSumMm`, explicit `reviewedRightRawZIntervalMm: [lower, upper]` for the analyzed local bracket, and positive uncertainty bounds: `n1DatumUncertaintyMm`, `sameWorldXYRowUncertaintyPx` (including residual parallax/roll), `localLinearityUncertaintyMm`, and `rawZUncertaintyMm` (at least 0.02 mm). These are evidence inputs, not provided calibration defaults.

`bottomAlignmentEvidence` maps `N1` and `N2` to an `image` reference and a `positionEvidence` reference (each has absolute `path` and `sha256`). The image must be the native report's `afterImages.bottom` capture. Alignment reports must match the side sequence JVM/configuration and that head's XY/A/B. `poses` maps the five names above to:

```json
{
  "positionEvidence": {"path": "absolute native report path", "sha256": "exact digest"},
  "frames": [
    {
      "image": {"path": "absolute HD frame path", "sha256": "exact digest"},
      "roi": [580, 70, 620, 350],
      "seed": [600, 100],
      "thresholds": [40, 80],
      "polarity": "dark",
      "annotationUncertaintyPx": 0.5
    }
  ]
}
```

The shown pixels/thresholds are synthetic format examples; choose them from actual frames and supply at least two frames. ROI bounds are half-open full-image pixel coordinates; the seed is a full-image pixel inside the manually identified shaft. Dark/bright segmentation uses grayscale. The seed's 8-connected component must remain present at every threshold, contain at least three pixels, and not touch the ROI's sides or bottom. Its top may leave the ROI. Its bottommost pixel row is the endpoint estimate; threshold hulls and the declared annotation bound (at least half a pixel) produce frame intervals. All frame intervals and the repeated reference are combined conservatively.

Native reports must have a supported successful terminal status (survey, Z observation, position barrier, LED restore or native home), and show `controllerPositionVerified: true`, `uncertainCompletion: false`, no error, full XYZAB under `reported` or `after.reported`, and request JVM/configuration identity. Hashes are checked against the same bytes parsed/decoded. All reports must share JVM/configuration and A/B. Raw XY stays fixed within each head's sequence; differing head offsets mean it need not match between N1 and N2.

The N1 dither must resolve a negative pixel-row/raw-Z slope. The right bracket must resolve a positive slope, with overlapping slope-magnitude intervals. Full endpoint uncertainty must be inside the right bracket; extrapolation is rejected. All endpoint/target interval corners are evaluated. The output bounds satisfy:

`right tip offset = reference N1 height + matching right raw Z - coupled Z sum`

For a reviewed nominal sum of 63 mm and N1 reference height 31.5 mm this becomes matching right raw Z minus 31.5 mm. Reported-Z, N1 datum, and local-linearity uncertainties widen the result. The result is a conditional interval, not a statistical confidence interval or exact calibration. Insufficient pixel resolution may reject a 1 mm dither; improve the view rather than pretending the slope or bracket is resolved.

Run `python3 automation/paste/analysis/tip_height_interval.py --request /absolute/request.json --output /absolute/new-result.json`. Output creation is exclusive. Synthetic tests are in `test_tip_height_interval.py`; no real height has been measured by implementing or testing this helper.
