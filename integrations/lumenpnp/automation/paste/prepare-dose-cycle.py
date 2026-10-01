#!/usr/bin/env python3
"""Validate a reviewed paste dose cycle; optionally prepare detached native evidence.

Default mode is local and read-only. ``--prepare-native`` explicitly permits a
read-only native position barrier and disconnected formatter preview. Neither
mode dispatches the B-dose/retract/Z-lift execution action.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOSE_VALUES = (2, 4, 6, 20)


def read(path):
    return json.loads(Path(path).read_text())


def evidence(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def observe_helpers():
    module_path = ROOT / "automation/paste/observe-z-step.py"
    spec = importlib.util.spec_from_file_location("paste_z_observation_helpers", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_args(args, now_ms):
    for label, path in (("source", args.source), ("image", args.image), ("profile", args.profile),
                        ("previous report", args.previous_report), ("prime ledger", args.prime_ledger),
                        ("prior ledger", args.prior_ledger), ("carryover", args.carryover)):
        if not path.is_file():
            raise ValueError(f"{label} file is missing: {path}")
    if args.dose not in DOSE_VALUES or args.retract not in DOSE_VALUES:
        raise ValueError("dose and retract must each be one of 2, 4, 6, or 20 degrees")
    if not 0 <= args.dwell <= 1000:
        raise ValueError("dwell must be an integer from 0 through 1000 ms")
    image_ms = args.image.stat().st_mtime_ns // 1_000_000
    if image_ms > now_ms or now_ms - image_ms > 300_000:
        raise ValueError("reviewed image must be no more than five minutes old")
    source = read(args.source)
    previous = read(args.previous_report)
    profile = read(args.profile)
    prime = read(args.prime_ledger)
    prior = read(args.prior_ledger)
    carry = read(args.carryover)
    if (source.get("error") or not source.get("status", "").startswith("completed-")
            or source.get("uncertainCompletion") is not False
            or source.get("controllerPositionVerified") is not True
            or not source.get("afterQuerySnapshot", {}).get("raw")):
        raise ValueError("source must be a verified completed report with an after-query pose")
    if profile.get("measured") is not True or profile.get("flowCalibrated") is not False:
        raise ValueError("profile must be a measured, non-flow-calibrated receiving profile")
    if source.get("request", {}).get("jvmStartMs") != profile.get("jvmStartMs"):
        raise ValueError("source and receiving profile must belong to the same JVM session")
    if source.get("request", {}).get("liveConfigurationSha256") != profile.get("liveConfigurationSha256"):
        raise ValueError("source and receiving profile configuration hashes differ")
    if previous.get("request", {}).get("jvmStartMs") != profile.get("jvmStartMs"):
        raise ValueError("previous report and receiving profile must belong to the same JVM session")
    raw = source["afterQuerySnapshot"]["raw"]
    pose = profile.get("rawPose", {})
    for axis in ("X", "Y", "Z", "A"):
        try:
            profiled, current = float(pose[axis]), float(raw[axis])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"receiving profile and source must contain finite {axis} coordinates")
        if not math.isfinite(profiled) or not math.isfinite(current) or abs(profiled - current) > 0.0001:
            raise ValueError(f"receiving profile must bind the exact finite source {axis} coordinate")
    try:
        if not math.isfinite(float(raw["B"])):
            raise ValueError("source B coordinate must be finite")
    except (KeyError, TypeError, ValueError):
        raise ValueError("source B coordinate must be finite")
    ledger_path = previous.get("ledgerPath")
    if not ledger_path:
        raise ValueError("previous report does not identify its shared commissioning ledger")
    args.previous_report_ledger = Path(ledger_path).resolve()
    if not args.previous_report_ledger.is_file():
        raise ValueError("shared commissioning ledger identified by report is missing")
    ledger = read(args.previous_report_ledger)
    if (ledger.get("status") != "verified" or ledger.get("sessionId") != profile.get("sessionId")
            or ledger.get("lastVerifiedB") != raw.get("B")):
        raise ValueError("previous report ledger must be verified at the source B position")
    terminal = ("completed-commissioning-stroke-awaiting-observation",
                "completed-dose-cycle-awaiting-observation")
    last_entry = ledger.get("entries", [])[-1] if ledger.get("entries") else None
    report_id = previous.get("id")
    if (previous.get("status") not in terminal or previous.get("uncertainCompletion") is not False
            or previous.get("completedLedgerSha256") != evidence(args.previous_report_ledger)["sha256"]
            or not last_entry
            or (last_entry.get("cycleId") or last_entry.get("requestId")) != report_id):
        raise ValueError("previous report must bind the exact verified shared ledger")
    if prime.get("status") != "verified" or prior.get("status") != "verified":
        raise ValueError("prime and prior-session ledgers must be verified")
    if carry.get("primeLedgerSha256") != evidence(args.prime_ledger)["sha256"] or carry.get("priorLedgerSha256") != evidence(args.prior_ledger)["sha256"]:
        raise ValueError("carryover record must hash-bind the supplied prime and prior ledgers")
    def positive_integer(value):
        try:
            n = float(value)
            return math.isfinite(n) and n > 0 and n.is_integer()
        except (TypeError, ValueError):
            return False
    accounting = prime.get("postResetCarryover", {})
    if (carry.get("schema") != 1 or carry.get("sessionId") != profile.get("sessionId")
            or carry.get("syringeId") != profile.get("syringeId")
            or prime.get("sessionId") != carry.get("sessionId")
            or carry.get("manualDisplacementUnknown") is not True
            or not positive_integer(carry.get("maximumAbsoluteDegrees"))
            or carry.get("startB") != prime.get("lastVerifiedB")
            or carry.get("verifiedPrimeDegrees") != prime.get("reservedDegrees")
            or carry.get("priorGrossDegrees") != prior.get("reservedDegrees")
            or carry.get("priorSessionId") != prior.get("sessionId")
            or accounting.get("priorGrossDegrees") != carry.get("priorGrossDegrees")
            or accounting.get("manualDisplacementUnknown") is not True
            or accounting.get("priorSessionId") != carry.get("priorSessionId")
            or accounting.get("priorLedgerSha256") != carry.get("priorLedgerSha256")):
        raise ValueError("carryover, prime ledger and prior ledger accounting fields disagree")
    if profile.get("sessionId") != ledger.get("sessionId") or profile.get("syringeId") != ledger.get("syringeId"):
        raise ValueError("profile and commissioning ledger must identify the same session and syringe")
    if previous.get("finishedAt") and previous["finishedAt"] > datetime_from_ms(image_ms):
        raise ValueError("reviewed image must be captured after the prior report completed")
    if not args.review:
        raise ValueError("a concise pose/clearance review record is required")
    return {"source": source, "previous": previous, "profile": profile, "ledger": ledger,
            "imageCapturedMs": image_ms, "nowMs": now_ms}


def datetime_from_ms(value):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(value / 1000)) + ".%03dZ" % (value % 1000)


def dispatch(action, report, helpers):
    # Existing helper already polls for a terminal report and fails closed.
    return helpers.dispatch(action, report)


def prepare_native(args, validated):
    helpers = observe_helpers()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    now_ms = int(time.time() * 1000)
    source = validated["source"]
    snapshot = source["afterQuerySnapshot"]

    barrier_plan = ROOT / "automation/plans/paste-position-barrier-request.json"
    barrier_request = read(barrier_plan)
    barrier_request.update(id=str(uuid.uuid4()), createdMs=now_ms,
                           expectedRaw=snapshot["raw"], expectedDriver=snapshot["driver"],
                           expectedNativePoses=snapshot["nativePoses"], operator=args.review)
    config_hash = source.get("liveConfigurationSha256", source["request"].get("liveConfigurationSha256"))
    if config_hash != barrier_request.get("liveConfigurationSha256"):
        raise ValueError("source does not match the currently installed barrier configuration")
    if source["request"].get("jvmStartMs") != barrier_request.get("jvmStartMs"):
        raise ValueError("source is not from the current OpenPnP JVM")
    save(barrier_plan, barrier_request)
    barrier_report = ROOT / f"automation/evidence/paste-position-barrier-{barrier_request['id']}/report.json"
    dispatch("paste-position-barrier", barrier_report, helpers)

    preview_id = str(uuid.uuid4())
    preview_request = {
        "schema": 1,
        "scope": "single-native-B-dose-retract-Z-lift-cycle-preview",
        "enabled": False,
        "id": preview_id,
        "sessionId": validated["profile"]["sessionId"],
        "createdMs": int(time.time() * 1000),
        "jvmStartMs": barrier_request["jvmStartMs"],
        "liveConfigurationSha256": barrier_request["liveConfigurationSha256"],
        "doseDegrees": args.dose,
        "retractDegrees": args.retract,
        "dwellMilliseconds": args.dwell,
        "liftDeltaMm": -5,
        "dispenseSpeedFraction": 0.05,
        "retractSpeedFraction": 0.05,
        "liftSpeedFraction": 1.0,
        "expectedRaw": snapshot["raw"],
        "expectedDriver": snapshot["driver"],
        "expectedNativePoses": snapshot["nativePoses"],
        "barrierEvidence": evidence(barrier_report),
    }
    preview_plan = ROOT / "automation/plans/paste-dose-cycle-preview-request.json"
    save(preview_plan, preview_request)
    preview_report = ROOT / f"automation/evidence/paste-dose-cycle-preview-{preview_id}/report.json"
    dispatch("paste-dose-cycle-preview", preview_report, helpers)

    build_input = {
        "schema": 1,
        "scope": "reviewed-paste-dose-cycle-input",
        "barrierPath": str(barrier_report),
        "profilePath": str(args.profile.resolve()),
        "reviewedImagePath": str(args.image.resolve()),
        "reviewedImageSha256": evidence(args.image)["sha256"],
        "reviewedPoseImageSha256": evidence(args.image)["sha256"],
        "poseAndClearanceReviewed": True,
        "liftClearanceReviewed": True,
        "imageCapturedMs": validated["imageCapturedMs"],
        "reviewedMs": now_ms,
        "nativePreviewPath": str(preview_report),
        "doseDegrees": args.dose,
        "retractDegrees": args.retract,
        "dwellMilliseconds": args.dwell,
        "primeLedgerPath": str(args.prime_ledger.resolve()),
        "priorLedgerPath": str(args.prior_ledger.resolve()),
        "carryoverPath": str(args.carryover.resolve()),
        "previousCommissioningLedgerPath": str(args.previous_report_ledger.resolve()),
        "previousReportPath": str(args.previous_report.resolve()),
    }
    input_path = args.output_dir / "input.json"
    request_path = args.output_dir / "request.json"
    save(input_path, build_input)
    subprocess.run(["node", str(ROOT / "automation/scripts/build_paste_dose_cycle_request.cjs"),
                    str(input_path), str(request_path)], cwd=ROOT, check=True)
    print(json.dumps({"outputDirectory": str(args.output_dir.resolve()),
                      "request": str(request_path.resolve()), "enabled": False,
                      "executionDispatched": False}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="verified terminal report whose exact pose is current")
    parser.add_argument("--image", type=Path, required=True, help="fresh reviewed camera image")
    parser.add_argument("--profile", type=Path, required=True, help="same-session measured receiving-gap profile")
    parser.add_argument("--previous-report", type=Path, required=True, help="previous verified B stroke/cycle report")
    parser.add_argument("--prime-ledger", type=Path, required=True)
    parser.add_argument("--prior-ledger", type=Path, required=True)
    parser.add_argument("--carryover", type=Path, required=True)
    parser.add_argument("--dose", type=int, choices=DOSE_VALUES, required=True)
    parser.add_argument("--retract", type=int, choices=DOSE_VALUES, required=True)
    parser.add_argument("--dwell", type=int, choices=range(0, 1001), required=True, metavar="0..1000")
    parser.add_argument("--review", required=True, help="short pose and both-head clearance review record")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--prepare-native", action="store_true",
                        help="explicitly run read-only position barrier and disconnected formatter preview")
    args = parser.parse_args()
    args.source = args.source.resolve()
    args.image = args.image.resolve()
    args.profile = args.profile.resolve()
    args.previous_report = args.previous_report.resolve()
    args.prime_ledger = args.prime_ledger.resolve()
    args.prior_ledger = args.prior_ledger.resolve()
    args.carryover = args.carryover.resolve()
    args.output_dir = args.output_dir.resolve()
    validated = validate_args(args, int(time.time() * 1000))
    summary = {"preliminaryInputChecksPassed": True, "nativePreparation": args.prepare_native,
               "fullCycleRequestBuilt": False,
               "executionDispatched": False, "sourceId": validated["source"].get("id"),
               "previousReportId": validated["previous"].get("id"),
               "pose": validated["source"]["afterQuerySnapshot"]["raw"],
               "doseDegrees": args.dose, "retractDegrees": args.retract,
               "dwellMilliseconds": args.dwell, "outputDirectory": str(args.output_dir)}
    if not args.prepare_native:
        print(json.dumps(summary, indent=2))
        return
    prepare_native(args, validated)


if __name__ == "__main__":
    main()
