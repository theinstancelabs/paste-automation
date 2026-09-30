# Current-plane needle-end observation

`needle_centroid.py` repeats a threshold-sensitivity measurement on a manually selected feature in stationary bottom-camera images. It reads verified completed survey records and their saved raw images; it does not access cameras or machine controls. It requires matching JVM/configuration and unchanged reported Z/A/B across all frames.

Recorded hashes bind the exact report/image bytes read for this analysis. Existing survey records do not contain capture-time image hashes, so this is not proof that an image remained unchanged since capture. Preserve the original evidence directory and review provenance separately.

Example command structure (use actual saved survey paths and a manually reviewed ROI):

```sh
python3 automation/paste/analysis/needle_centroid.py \
  --report /absolute/first-survey/report.json \
  --report /absolute/second-survey/report.json \
  --roi 930 522 983 554 --channel G \
  --thresholds 90 110 130 150 170 190 210 230 \
  --output /absolute/new-observation.json
python3 -m unittest discover -s automation/paste/analysis -p test_needle_centroid.py
```

ROI and thresholds above describe one observation, not defaults or calibration. For each threshold the tool selects the largest eight-connected component of at least three pixels inside the ROI. It reports component count, tied-area ambiguity and ROI-edge clipping. Review the image and every threshold; selection can switch between a reflection and the needle end. The software deliberately does not confirm feature identity.

Coordinates use raw pixel indices: pixel `(0,0)` is the top-left pixel center, X points right, Y points down. A 1920×1080 image has geometric center `(959.5,539.5)`. This is not proof of the camera's calibrated optical principal point. Unlike the area-mask tool's boundary-origin convention, this tool uses the familiar integer pixel-center convention explicitly.

Retain actual observation results and hashed evidence reports locally. A bright feature translating consistently with observed controller movements supports current-plane alignment, but does not by itself identify the lumen or calibrate the substrate plane. Enlarging the ROI to cover multiple positions can admit a brighter part of the hub or clamp; reject thresholds that select those features rather than averaging their centroids into the needle estimate.

With verified movements spanning both raw X and raw Y, `--fit-current-plane` adds a least-squares local image response matrix (pixel X/Y rows, raw X/Y millimeter columns), residuals, spread of repeated returns, and a provisional raw position corresponding to the geometric image center. It refuses collinear motion evidence, missing threshold components, ROI-edge clipping and tied-area ambiguity. This fit does not produce commands or calibrated head offsets; it assumes the operator identified the same feature across all frames. Choose a reviewed ROI and threshold range that isolate that feature throughout the full observation series.

Threshold spread is sensitivity to segmentation, not total uncertainty. A conservative initial visual uncertainty of roughly one pixel exceeds the small threshold spread; glare, focus, needle asymmetry and lens geometry may add systematic error. Use recorded ±X and ±Y movements and returns to separate image scale/cross-coupling and repeatability. Save a provisional current-plane alignment separately from machine head offsets. Unknown tip height, camera tilt and distortion still prevent claiming substrate-plane XY calibration, Z clearance, or paste placement readiness. No settings are corrected automatically.
