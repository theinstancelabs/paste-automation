#!/usr/bin/env python3
"""Offline before/after measurements for the four D26/D27 trial-14 pads.

Uses a fixed, visually unchanged left reference patch for small translation
registration, then measures new dark coverage only where the before image shows
bright bare pad. This is a 2D image estimate, not paste volume or acceptance.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from PIL import Image

MM_PER_PIXEL = 0.01068
REFERENCE_ROI = (100, 200, 550, 700)
# Pad windows were selected around the two bright bare D26/D27 pads in each
# same-reference capture. Their centers are estimated from the before image.
PAD_WINDOWS = {
    "D26.1": (810, 470, 940, 600),
    "D26.2": (960, 470, 1090, 600),
    "D27.1": (810, 470, 940, 600),
    "D27.2": (960, 470, 1090, 600),
}
# Profile CAD mapping for the two trial references. Pad numbering is not
# globally ordered: D26/D27 pad 1 is image-left and lower raw X; R27 pad 1 is
# image-right and higher raw X. Keep the trial labels tied to this mapping.
PAD_LAYOUT = {
    "D26.1": {"cadPadNumber": 1, "imageSide": "left"},
    "D26.2": {"cadPadNumber": 2, "imageSide": "right"},
    "D27.1": {"cadPadNumber": 1, "imageSide": "left"},
    "D27.2": {"cadPadNumber": 2, "imageSide": "right"},
}
BRIGHT_MIN = 200
GREEN_DROP_MIN = 35


def _load(path):
    return Image.open(path).convert("RGB")


def _registration(before, after):
    """Return the after-image translation minimizing green MAE in fixed ROI."""
    w, h = before.size
    x0, y0, x1, y1 = REFERENCE_ROI
    if not (0 <= x0 < x1 < w and 0 <= y0 < y1 < h):
        raise ValueError("Fixed reference ROI does not fit image")
    bp, ap = before.load(), after.load()
    candidates = []
    for dy in range(-5, 6):
        for dx in range(-5, 6):
            values = [
                abs(bp[x, y][1] - ap[x + dx, y + dy][1])
                for y in range(y0 + 5, y1 - 5, 8)
                for x in range(x0 + 5, x1 - 5, 8)
            ]
            candidates.append((sum(values) / len(values), dx, dy))
    error, dx, dy = min(candidates)
    if abs(dx) == 5 or abs(dy) == 5 or error > 15:
        raise ValueError("Left reference patch registration unresolved")
    return dx, dy, error


def _bright_center(before_pixels, window):
    x0, y0, x1, y1 = window
    pts = [(x, y) for y in range(y0, y1) for x in range(x0, x1)
           if min(before_pixels[x, y]) > BRIGHT_MIN]
    if len(pts) < 1000:
        raise ValueError(f"Insufficient bright bare pad pixels in {window}")
    return len(pts), (sum(x for x, _ in pts) / len(pts),
                      sum(y for _, y in pts) / len(pts))


def _largest_component(mask):
    """Connected-component pixel list using 8-neighbor connectivity."""
    height = len(mask)
    width = len(mask[0]) if height else 0
    seen = set()
    largest = []
    for y in range(height):
        for x in range(width):
            if not mask[y][x] or (x, y) in seen:
                continue
            stack = [(x, y)]
            seen.add((x, y))
            component = []
            while stack:
                cx, cy = stack.pop()
                component.append((cx, cy))
                for ny in range(max(0, cy - 1), min(height, cy + 2)):
                    for nx in range(max(0, cx - 1), min(width, cx + 2)):
                        if mask[ny][nx] and (nx, ny) not in seen:
                            seen.add((nx, ny))
                            stack.append((nx, ny))
            if len(component) > len(largest):
                largest = component
    return largest


def measure_pad(before_pixels, after_pixels, window, dx, dy, name):
    x0, y0, x1, y1 = window
    bright_count, (cx, cy) = _bright_center(before_pixels, window)
    mask = []
    for y in range(y0, y1):
        row = []
        for x in range(x0, x1):
            b = before_pixels[x, y]
            a = after_pixels[x + dx, y + dy]
            row.append(min(b) > BRIGHT_MIN and b[1] - a[1] > GREEN_DROP_MIN)
        mask.append(row)
    blob = _largest_component(mask)
    area_px = len(blob)
    area_mm2 = area_px * MM_PER_PIXEL * MM_PER_PIXEL
    if blob:
        dot_x = x0 + sum(x for x, _ in blob) / area_px
        dot_y = y0 + sum(y for _, y in blob) / area_px
        off_x, off_y = dot_x - cx, dot_y - cy
        bbox = [x0 + min(x for x, _ in blob), y0 + min(y for _, y in blob),
                x0 + max(x for x, _ in blob) + 1, y0 + max(y for _, y in blob) + 1]
    else:
        dot_x = dot_y = off_x = off_y = None
        bbox = None
    return {
        "padId": name,
        "cadMapping": PAD_LAYOUT[name],
        "padWindowPx": list(window),
        "brightBarePadPixels": bright_count,
        "beforeBrightPadCenterPx": [cx, cy],
        "newCoveragePixels": area_px,
        "projectedAreaMm2": area_mm2,
        "equivalentDiameterMm": 2 * math.sqrt(area_mm2 / math.pi) if area_px else 0.0,
        "coverageCentroidPx": [dot_x, dot_y] if blob else None,
        "offsetFromBeforeBrightPadCenterPx": [off_x, off_y] if blob else None,
        "offsetFromBeforeBrightPadCenterMm": [off_x * MM_PER_PIXEL, off_y * MM_PER_PIXEL] if blob else None,
        "coverageBoundingBoxPx": bbox,
    }


def measure(before_paths, after_paths):
    if len(before_paths) != 2 or len(after_paths) != 2:
        raise ValueError("Pass the D26 and D27 before/after paths in matching order")
    pads = []
    registrations = {}
    pairs = {}
    for name, before_path, after_path in zip(("D26", "D27"), before_paths, after_paths):
        before, after = _load(before_path), _load(after_path)
        if before.size != after.size:
            raise ValueError(f"{name} image dimensions differ")
        dx, dy, error = _registration(before, after)
        registrations[name] = {
            "translationPx": [dx, dy],
            "referenceRoiPx": list(REFERENCE_ROI),
            "referenceGreenMae": error,
        }
        pairs[name] = {
            "before": _evidence(before_path),
            "after": _evidence(after_path),
        }
        before_pixels, after_pixels = before.load(), after.load()
        for suffix in ("1", "2"):
            pad_id = f"{name}.{suffix}"
            pads.append(measure_pad(before_pixels, after_pixels, PAD_WINDOWS[pad_id], dx, dy, pad_id))
    areas = [p["projectedAreaMm2"] for p in pads]
    mean = sum(areas) / len(areas)
    cv = math.sqrt(sum((a - mean) ** 2 for a in areas) / len(areas)) / mean if mean else None
    return {
        "schema": 1,
        "scope": "trial14-D26-D27-two-dimensional-new-pad-coverage",
        "imagePairs": pairs,
        "registration": registrations,
        "thresholds": {
            "brightBarePadMinimumAllRgbChannelsExclusive": BRIGHT_MIN,
            "newCoverageMinimumGreenChannelDropExclusive": GREEN_DROP_MIN,
            "mmPerPixel": MM_PER_PIXEL,
            "areaCvDefinition": "population standard deviation divided by mean across four pad areas",
        },
        "cadMappingReview": {
            "basis": "D26/D27 CAD pad numbering and left/right order cross-checked against the local reviewed profile",
            "profileCoordinatesIncluded": False,
            "scope": "D26/D27 only; pad-number side order is not generalizable to R27",
        },
        "pads": pads,
        "fourPadAreaCoefficientOfVariation": cv,
        "physicalAcceptanceEstablished": False,
        "pasteVolumeMeasured": False,
        "limitations": [
            "Projected area is thresholded 2D visible coverage, not paste volume.",
            "Centroids are measured from pixels that were bright bare pad in the before image and darkened after registration.",
            "Lighting, focus, board flex, and partial occlusion can affect thresholded area and centroid.",
            "The left reference patch assumes no paste change there; no rotation or scale correction is made.",
        ],
    }


def _evidence(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", nargs=2, required=True, metavar=("D26", "D27"))
    parser.add_argument("--after", nargs=2, required=True, metavar=("D26", "D27"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = measure(args.before, args.after)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
