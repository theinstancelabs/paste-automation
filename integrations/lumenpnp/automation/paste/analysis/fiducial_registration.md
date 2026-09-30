# Three-fiducial registration review

`fiducial_registration.py` reads existing verified camera-survey reports, their raw top images, and the canonical KiCad board. It produces source-hashed offline rigid and similarity fits; it never changes OpenPnP registration or dispatches motion.

Prepare a JSON request with `board`, `reports` mapping exactly `FID1`, `FID2`, `FID3` to report paths, an explicit integer pixel `roi`, integer `thresholds`, and optional `localImageJacobianPixelsPerMm` (2×2). The Jacobian maps camera displacement to feature image displacement and must be independently observed at the current imaging plane. Omitting it retains uncorrected camera centers.

```sh
python3 fiducial_registration.py request.json output.json
python3 -m unittest test_fiducial_registration.py
```

The output is created exclusively. Dependencies are Python3, Pillow, adjacent `needle_centroid.py`/`deposit_metrics.py`, the source-only KiCad parser in `../pads/extract_ftp_pads.py`, and `../prepare-survey-request.py` for verified source-state checks.

The helper requires three same-session/configuration/fixed-ZAB survey completions. A manually selected red-channel connected component must remain unclipped and within two pixels of the raw geometric image center. It retains threshold-dependent areas/centroids and both the uncorrected and locally corrected fits. The geometric center is not assumed to be an independently calibrated optical principal point.

The KiCad file uses negative Y for these front-side fiducials. Output preserves those raw source coordinates and explicitly converts to the positive-Y front-board frame with `(x, -y)`, consistent with the board/Gerber frame. It never reads old modified board XML coordinates. Only single centered circular front-copper fiducials are supported.

Rigid fitting holds scale at1. Similarity fitting estimates one common scale and rotation; it does not fit shear or separate X/Y scales. The offline review gates are scale0.99–1.01 and maximum point residual0.08mm. A free three-point affine transform is intentionally unavailable because it could exactly absorb a wrong fiducial identity. All fits, residuals and pass flags are retained, including failures.

The0.05mm uncertainty allowance is a review allowance, not a calibrated confidence interval. Camera-centering repeatability, approach direction, local Jacobian uncertainty, lens calibration and physical fiducial identity remain separate evidence. Independent checks of actual resistor pads are required before treating a fit as physical registration. Output always records that physical registration is not established and machine configuration has not changed.
