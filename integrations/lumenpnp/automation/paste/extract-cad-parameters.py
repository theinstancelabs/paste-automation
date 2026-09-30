#!/usr/bin/env python3
"""Read nominal FreeCAD gear parameters without opening or modifying CAD files."""
import argparse, hashlib, json, math, pathlib, subprocess, zipfile
import xml.etree.ElementTree as ET


def gear(path):
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("Document.xml"))
    values = {}
    for name, tag, cast in (("teeth", "Integer", int), ("module", "Float", float)):
        matches = root.findall(f".//ObjectData/Object/Properties/Property[@name='{name}']/{tag}")
        if len(matches) != 1:
            raise ValueError(f"Expected one {name} property in {path}")
        values[name] = cast(matches[0].get("value"))
        if not math.isfinite(values[name]) or values[name] <= 0:
            raise ValueError(f"Invalid {name}")
    return {"file": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), **values}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hardware_repo", type=pathlib.Path)
    parser.add_argument("--needle-length-inch", type=float, required=True)
    parser.add_argument("--screw-pitch-mm", type=float)
    parser.add_argument("--syringe-bore-mm", type=float)
    args = parser.parse_args()
    for value in (args.needle_length_inch, args.screw_pitch_mm, args.syringe_bore_mm):
        if value is not None and (not math.isfinite(value) or value <= 0):
            parser.error("Dimensions must be finite and positive")
    if args.syringe_bore_mm is not None and args.screw_pitch_mm is None:
        parser.error("Bore-based volume requires an explicit screw pitch")
    repo = args.hardware_repo.resolve()
    motor = gear(repo / "cad/FDM/extruder-gear.FCStd")
    syringe = gear(repo / "cad/FDM/cartridge-gear.FCStd")
    if motor["module"] != syringe["module"]:
        raise ValueError("Gear modules differ")
    ratio = motor["teeth"] / syringe["teeth"]
    record = {"schema": 1, "nominalOnly": True, "physicalCalibrationEstablished": False,
              "hardwareCommit": subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip(),
              "motorGear": motor, "syringeGear": syringe,
              "syringeRevolutionsPerMotorRevolution": ratio,
              "userSpecifiedNeedleLengthMm": args.needle_length_inch * 25.4,
              "installedTipOffsetMm": None,
              "explicitUnverifiedInputs": {"screwPitchMm": args.screw_pitch_mm, "syringeBoreMm": args.syringe_bore_mm}}
    if args.screw_pitch_mm is not None:
        travel = ratio * args.screw_pitch_mm
        record["conditionalPlungerMmPerMotorRevolution"] = travel
        if args.syringe_bore_mm is not None:
            record["conditionalDisplacementMicrolitersPerMotorRevolution"] = math.pi * args.syringe_bore_mm**2 / 4 * travel
    record["limits"] = "Gear ratio magnitude only; no B-axis direction/unit mapping, installed tip offset, priming dose or delivered-paste prediction is established. Supplied pitch/bore are assumptions until verified."
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
