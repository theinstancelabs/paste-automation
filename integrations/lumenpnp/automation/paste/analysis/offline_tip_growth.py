#!/usr/bin/env python3
"""Offline incremental-filament check for a fixed, registered camera view.

`no-change` means no new connected neutral filament was resolved relative to
this reference image; it never certifies a clean tip or stopped flow.
"""
import argparse
from collections import deque
import json
from pathlib import Path
from PIL import Image


def analyze(baseline, frame, roi, min_growth=3):
    """Return inspect/growth/no-change, using an inclusive (x0,y0,x1,y1) ROI."""
    x0, y0, x1, y1 = roi
    def read(path):
        im = Image.open(path).convert("HSV")
        if x0 < 0 or y0 < 0 or x1 > im.width or y1 > im.height or x0 >= x1 or y0 >= y1:
            return im.size, []
        return im.size, [[(lambda p: p[1] <= 110 and p[2] > 75)(im.getpixel((x, y)))
                          for x in range(x0, x1)] for y in range(y0, y1)]
    size0, ref = read(baseline); size, mask = read(frame)
    if size != size0 or not ref or not mask or len(ref[0]) < 3:
        return {"decision": "inspect", "reason": "image_size_or_roi_mismatch"}
    # Resolve baseline's shaft axis and tip from multi-pixel neutral rows.
    counts = [sum(row) for row in ref]
    rows = [i for i, n in enumerate(counts) if n >= 2]
    if len(rows) < 12:
        return {"decision": "inspect", "reason": "reference_shaft_not_resolved"}
    end = max(rows); start = min(i for i in rows if i <= end)
    if any(counts[i] < 2 for i in range(end - 10, end + 1)):
        return {"decision": "inspect", "reason": "reference_shaft_discontinuous"}
    def center(m, a, b):
        pts = [x0 + x for y in range(a, b + 1) for x, v in enumerate(m[y]) if v]
        return sum(pts) / len(pts) if pts else None
    cx = center(ref, end - 8, end - 2)
    fcounts = [sum(row) for row in mask]
    frows = [i for i, n in enumerate(fcounts) if n >= 2]
    if not frows or abs(min(frows) - start) > 1 or any(fcounts[i] < 2 for i in range(end - 10, end + 1)):
        return {"decision": "inspect", "reason": "shaft_occluded_or_misaligned", "baseline_tip_y": y0 + end}
    fcx = center(mask, end - 8, end - 2)
    if fcx is None or abs(fcx - cx) > 1:
        return {"decision": "inspect", "reason": "shaft_axis_shift", "baseline_tip_y": y0 + end}
    # Flood only pixels connected 8-neighbor to the resolved metal endpoint.
    q = deque((x, end) for x, v in enumerate(mask[end]) if v and abs(x0 + x - cx) <= 2)
    seen = set(q); lowest = end
    while q:
        x, y = q.popleft(); lowest = max(lowest, y)
        for yy in range(y, min(len(mask), y + 2)):
            for xx in range(max(0, x - 1), min(len(mask[0]), x + 2)):
                if yy > y and mask[yy][xx] and (xx, yy) not in seen:
                    seen.add((xx, yy)); q.append((xx, yy))
    growth = lowest - end
    return {"decision": "growth" if growth >= min_growth else "no-change",
            "reason": "connected_neutral_extension" if growth >= min_growth else "below_growth_threshold",
            "baseline_tip_y": y0 + end, "connected_extension_px": growth,
            "meaning": "incremental image evidence only; no-change does not mean clean or flow-stopped"}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", required=True, help="reference image at this fixed pose")
    ap.add_argument("--frames", nargs="+", required=True)
    ap.add_argument("--roi", nargs=4, type=int, required=True, metavar=("X0", "Y0", "X1", "Y1"),
                    help="explicit reviewed pixel crop; no camera-specific coordinates are assumed")
    ap.add_argument("--min-growth", type=int, default=3)
    a = ap.parse_args()
    print(json.dumps([{"frame": p, **analyze(a.baseline, p, tuple(a.roi), a.min_growth)} for p in a.frames], indent=2))

if __name__ == "__main__":
    main()
