# Repeatable deposit inspection

`deposit_metrics.py` measures reviewed binary pad and paste masks in a common image frame. It does not segment images automatically, command hardware, select a recipe, or declare a physical pass. Preserve the original before/after images; use a small model or operator to review segmentation and registration, then use this deterministic calculation for comparisons.

The measured X/Y pixel scales must describe the actual substrate plane and image processing. A bed-plane scale cannot be reused for the raised demo board. Rectified images may use equal scales; otherwise this tool assumes orthogonal image axes with separate X/Y scales. Perspective/shear requires rectification first. Do not silently align before/after images by their different paste features: use unchanged board features.

Provide 8-bit grayscale PNG masks, with exactly zero for background and255 for foreground. Each pad has its own unique ID and nonoverlapping mask; the paste mask includes tails and spill outside pads. All masks have identical dimensions. Include enough surrounding image to catch off-pad deposits. A connected deposit touching multiple pads is reported as a possible bridge, including diagonal8-connected pixels. Inspect the original image to distinguish a real bridge from segmentation noise or reflection.

Request shape (all paths are actual local files; source image references use absolute paths and their SHA-256 hashes):

```json
{
  "schema": 1,
  "masksReviewedAndAligned": true,
  "reviewer": "reviewer identifier",
  "segmentationMethod": "documented method and corrections",
  "registrationRecord": "record establishing common image frame",
  "scaleRecord": "record of scale at this substrate plane",
  "sourceImages": [{"path": "/absolute/after.png", "sha256": "actual SHA-256"}],
  "pasteMask": "/absolute/paste-mask.png",
  "pads": [{"id": "R1.1", "mask": "/absolute/R1.1-mask.png"}],
  "mmPerPixelX": 0.01,
  "mmPerPixelY": 0.01
}
```

The displayed scale is an illustrative value, not calibration. References to registration/scale identify the review records; the tool does not validate their metrology. Original image hashes and mask hashes are retained and original image references checked. Each mask hash describes the exact bytes decoded for measurement, and the request hash describes the exact bytes parsed. Mask review is an explicit claim, not software image validation.

Centroid offsets use the aligned mask's image frame: positive X is right and positive Y is down, with pixel centers at `(column + 0.5, row + 0.5)` relative to the top-left image origin. They are not native machine XY offsets. The output records this convention and eight-neighbor component connectivity explicitly.

```sh
python3 automation/paste/analysis/deposit_metrics.py request.json metrics.json
python3 -m unittest discover -s automation/paste/analysis -p test_deposit_metrics.py
```

The output refuses overwrite. It reports covered pad area/fraction, covered-region centroid offset, total touching-component area, spill outside all included pads, disconnected component count, possible bridges and cropped-edge deposits. Shared bridge areas deliberately remain shared in per-pad metrics; do not sum those areas across pads. The covered centroid is clipped to the pad; inspect full touching deposit/spill to detect a tail. Deposits not touching any pad still contribute to total spill.

These2D metrics do not establish paste volume or height. Use consistent imaging and reviewed segmentation for dose comparisons; freeze tolerances only after physical trials demonstrate useful outcomes. For repeatability, retain individual measurements and settings, compare several fresh pads and first deposits after a pause, and inspect bridges, strings, delayed flow and missed dots. A software-completed dose is not evidence of deposited paste.
