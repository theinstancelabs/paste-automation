"""Offline shape check for the coarse bright copper disk at a native keypoint."""
import math


def bright_disk_occupancy(image, center_xy, radius_px=40.0, threshold=100):
    """Return bright-pixel fraction inside a circular mask around a candidate.

    This deliberately checks the observed raw image pixels, rather than trusting
    the native locator's candidate metadata. Coordinates are image pixel indices.
    """
    from PIL import Image

    if not isinstance(image, Image.Image):
        raise ValueError('Pillow image required')
    if (not isinstance(center_xy, (list, tuple)) or len(center_xy) != 2
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in center_xy)
            or type(radius_px) not in (int, float) or not math.isfinite(radius_px) or radius_px <= 0
            or type(threshold) is not int or not 0 <= threshold <= 255):
        raise ValueError('Finite center, positive radius and byte threshold required')
    rgb = image.convert('RGB')
    cx, cy = map(float, center_xy)
    r = float(radius_px)
    x0, x1 = math.floor(cx-r), math.ceil(cx+r)
    y0, y1 = math.floor(cy-r), math.ceil(cy+r)
    if x0 < 0 or y0 < 0 or x1 >= rgb.width or y1 >= rgb.height:
        raise ValueError('Circle mask must fit fully inside the raw image')
    count = bright = 0
    for y in range(y0, y1+1):
        for x in range(x0, x1+1):
            if (x-cx)**2 + (y-cy)**2 <= r*r:
                count += 1
                if max(rgb.getpixel((x, y))) >= threshold:
                    bright += 1
    return {'radiusPx': r, 'threshold': threshold, 'pixels': count,
            'brightPixels': bright, 'occupancy': bright/count}


def require_bright_disk(image, center_xy, radius_px=40.0, threshold=100, min_occupancy=0.65):
    result = bright_disk_occupancy(image, center_xy, radius_px, threshold)
    if type(min_occupancy) not in (int, float) or not math.isfinite(min_occupancy) or not 0 < min_occupancy <= 1:
        raise ValueError('A finite occupancy threshold in (0, 1] is required')
    result['minimumOccupancy'] = float(min_occupancy)
    result['passes'] = result['occupancy'] >= min_occupancy
    return result
