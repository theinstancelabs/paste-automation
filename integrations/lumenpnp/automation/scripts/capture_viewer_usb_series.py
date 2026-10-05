#!/usr/bin/env python3
"""Capture a bounded series from the existing authenticated webcam viewer."""

import argparse
import datetime as dt
import json
import pathlib
import time
import urllib.error
import urllib.request

MAX_SECONDS = 3600
FETCH_TIMEOUT_SECONDS = 8
TOKEN_PATH = pathlib.Path("/home/lumen/lumenpnp/.local-viewer/token")


def parse_sample_times(value):
    try:
        samples = [float(part.strip()) for part in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("sample times must be comma-separated seconds") from exc
    if not samples or any(not (0 <= sample <= MAX_SECONDS) for sample in samples):
        raise argparse.ArgumentTypeError(f"sample times must be between 0 and {MAX_SECONDS} seconds")
    if samples != sorted(set(samples)):
        raise argparse.ArgumentTypeError("sample times must be strictly increasing")
    return samples


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def fetch_frame(request):
    with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seconds", type=int, default=60,
                        help="capture once per second for this many seconds (default: 60; max: 3600)")
    parser.add_argument("--sample-times", type=parse_sample_times, metavar="SECONDS",
                        help="capture at fixed offsets, e.g. 0,5,15,30,60; overrides --seconds")
    parser.add_argument("--contact-sheet", action="store_true",
                        help="also save a labeled contact sheet (requires Pillow)")
    args = parser.parse_args()

    if not 1 <= args.seconds <= MAX_SECONDS and args.sample_times is None:
        parser.error(f"--seconds must be between 1 and {MAX_SECONDS}")
    offsets = args.sample_times if args.sample_times is not None else list(range(args.seconds))
    out = pathlib.Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    manifest = {
        "source": "authenticated local viewer webcam endpoint",
        "started_at_utc": utc_now(),
        "schedule_seconds": offsets,
        "captures": [],
        "status": "running",
        "errors": [],
        "interpretation": "Frames require human review; this script does not assess framing, motion, nozzle visibility, or material presence.",
    }
    start = time.monotonic()
    try:
        token = TOKEN_PATH.read_text().strip()
        request = urllib.request.Request(
            "http://127.0.0.1:8765/frame/webcam",
            headers={"Authorization": "Bearer " + token},
        )
        for index, offset in enumerate(offsets):
            delay = start + offset - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            try:
                data = fetch_frame(request)
                if not data:
                    raise OSError("viewer returned an empty frame")
                # Record the wall clock and monotonic offset at completion of the frame read.
                captured_at = utc_now()
                elapsed = time.monotonic() - start
                filename = f"{index:04d}.jpg"
                (out / filename).write_bytes(data)
                manifest["captures"].append({
                    "file": filename,
                    "scheduled_elapsed_seconds": offset,
                    "elapsed_seconds": round(elapsed, 3),
                    "captured_at_utc": captured_at,
                    "bytes": len(data),
                    "status": "saved",
                })
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                manifest["errors"].append({
                    "scheduled_elapsed_seconds": offset,
                    "elapsed_seconds": round(time.monotonic() - start, 3),
                    "at_utc": utc_now(),
                    "error": f"{type(exc).__name__}: {exc}",
                })
                # Avoid retry loops; the next scheduled sample remains useful evidence.

        if args.contact_sheet and manifest["captures"]:
            try:
                from PIL import Image, ImageDraw

                thumbs = []
                for capture in manifest["captures"]:
                    image = Image.open(out / capture["file"]).convert("RGB")
                    image.thumbnail((480, 360))
                    tile = Image.new("RGB", (500, 400), "white")
                    tile.paste(image, ((500 - image.width) // 2, 10))
                    ImageDraw.Draw(tile).text((10, 375), capture["captured_at_utc"], fill="black")
                    thumbs.append(tile)
                columns = min(3, len(thumbs))
                rows = (len(thumbs) + columns - 1) // columns
                sheet = Image.new("RGB", (columns * 500, rows * 400), "#dddddd")
                for i, tile in enumerate(thumbs):
                    sheet.paste(tile, ((i % columns) * 500, (i // columns) * 400))
                sheet.save(out / "contact-sheet.jpg", quality=90)
                manifest["contact_sheet"] = "contact-sheet.jpg"
            except Exception as exc:
                manifest["errors"].append({"stage": "contact_sheet", "at_utc": utc_now(),
                                          "error": f"{type(exc).__name__}: {exc}"})
    except Exception as exc:
        # Never include request headers or token values in diagnostics.
        manifest["errors"].append({"stage": "setup", "at_utc": utc_now(),
                                  "error": f"{type(exc).__name__}: {exc}"})

    manifest["finished_at_utc"] = utc_now()
    manifest["elapsed_seconds"] = round(time.monotonic() - start, 3)
    manifest["status"] = "complete" if not manifest["errors"] and len(manifest["captures"]) == len(offsets) else (
        "partial" if manifest["captures"] else "failed"
    )
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Capture status: {manifest['status']} ({len(manifest['captures'])}/{len(offsets)} frames); manifest: {out / 'manifest.json'}")
    return 0 if manifest["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
