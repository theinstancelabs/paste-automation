# Selected-region image displacement

`image_region_translation.py` compares existing images without camera or machine access. Select distinct rigid features on each moving assembly and a stationary reference. Each ROI is `[left, top, right, bottom]` in the before image; matching searches the after image within explicit pixel radii.

```sh
python3 image_region_translation.py before.jpg after.jpg \
  --regions '{"left":[100,100,140,170],"right":[200,100,240,170],"fixed":[300,100,340,170]}' \
  --radius-x 3 --radius-y 6 --output review.json
python3 -m unittest test_image_region_translation.py
```

Coordinates above are illustrative pixel ROIs, not machine coordinates or a calibrated profile. Select actual regions from the images being reviewed. The output hashes the exact input bytes, lists three best integer matches, and flags search-boundary matches. Output creation is exclusive to prevent overwriting an earlier review. Dependencies: Python 3 and Pillow.

Positive image Y means downward. Comparing moving features against stationary references can corroborate physical motion direction. Lighting changes, repeated patterns, partial occlusion and perspective can produce false matches; inspect both originals and the candidate regions. A flat or repetitive reference can be ambiguous even without a boundary flag. The integer result and candidate differences are not a statistical confidence interval. Neither image displacement nor a commanded distance establishes absolute tip height, body clearance or safety of a longer motion.
