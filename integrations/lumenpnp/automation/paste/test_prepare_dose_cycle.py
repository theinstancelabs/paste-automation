import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

MODULE_PATH = Path(__file__).with_name("prepare-dose-cycle.py")
SPEC = importlib.util.spec_from_file_location("prepare_dose_cycle", MODULE_PATH)
PREP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREP)


class PrepareDoseCyclePreflightTests(unittest.TestCase):
    def fixture(self, root):
        root = Path(root)
        image = root / "review.png"
        image.write_bytes(b"reviewed-image")
        now_ms = int(time.time() * 1000)
        session, prior_session, syringe = "12345678-1234-1234-1234-123456789abc", "87654321-4321-4321-4321-cba987654321", "test-syringe"
        h = "a" * 64
        ledger_path = root / "commissioning-ledger.json"
        ledger = {"schema": 1, "scope": "signed-B-commissioning-strokes", "sessionId": session,
                  "syringeId": syringe, "startB": -10, "lastVerifiedB": -5,
                  "totalAbsoluteDegrees": 5, "status": "verified",
                  "entries": [{"requestId": "cycle-id", "cycleId": "cycle-id", "status": "verified"}]}
        ledger_path.write_text(json.dumps(ledger))
        ledger_hash = PREP.evidence(ledger_path)["sha256"]
        previous_path = root / "previous-report.json"
        report = {"id": "cycle-id", "status": "completed-dose-cycle-awaiting-observation",
                  "uncertainCompletion": False, "completedLedgerSha256": ledger_hash,
                  "ledgerPath": str(ledger_path), "finishedAt": "2000-01-01T00:00:00.000Z",
                  "request": {"jvmStartMs": 123, "liveConfigurationSha256": h},
                  "controllerPositionVerified": True,
                  "afterQuerySnapshot": {"raw": {"X": 1.0, "Y": 2.0, "Z": 3.0, "A": 4.0, "B": -5.0}}}
        previous_path.write_text(json.dumps(report))
        source_path = root / "source-report.json"
        source_path.write_text(json.dumps(report))
        profile_path = root / "profile.json"
        profile = {"sessionId": session, "syringeId": syringe, "jvmStartMs": 123,
                   "liveConfigurationSha256": h, "measured": True, "flowCalibrated": False,
                   "rawPose": {"X": 1.0, "Y": 2.0, "Z": 3.0, "A": 4.0}}
        profile_path.write_text(json.dumps(profile))
        prior_path = root / "prior-ledger.json"
        prior_path.write_text(json.dumps({"schema": 2, "sessionId": prior_session, "reservedDegrees": 900, "status": "verified"}))
        prior_hash = PREP.evidence(prior_path)["sha256"]
        prime_path = root / "prime-ledger.json"
        prime_path.write_text(json.dumps({"schema": 2, "sessionId": session, "lastVerifiedB": -10,
                                           "reservedDegrees": 95, "status": "verified",
                                           "postResetCarryover": {"priorGrossDegrees": 900,
                                               "manualDisplacementUnknown": True,
                                               "priorSessionId": prior_session,
                                               "priorLedgerSha256": prior_hash}}))
        prime_hash = PREP.evidence(prime_path)["sha256"]
        carry_path = root / "carryover.json"
        carry_path.write_text(json.dumps({"schema": 1, "sessionId": session, "syringeId": syringe,
                                           "primeLedgerSha256": prime_hash, "priorLedgerSha256": prior_hash,
                                           "priorSessionId": prior_session, "priorGrossDegrees": 900,
                                           "manualDisplacementUnknown": True, "verifiedPrimeDegrees": 95,
                                           "startB": -10, "maximumAbsoluteDegrees": 150}))
        return SimpleNamespace(source=source_path, image=image, profile=profile_path,
                               previous_report=previous_path, prime_ledger=prime_path,
                               prior_ledger=prior_path, carryover=carry_path,
                               dose=4, retract=2, dwell=200, review="profile and lift corridor checked",
                               output_dir=root / "out")

    def test_nonfinite_or_missing_profile_pose_fails_closed(self):
        for bad in ("missing", float("nan"), float("inf")):
            with self.subTest(value=bad), tempfile.TemporaryDirectory() as temporary:
                args = self.fixture(temporary)
                profile = json.loads(args.profile.read_text())
                if bad == "missing":
                    del profile["rawPose"]["X"]
                else:
                    profile["rawPose"]["X"] = bad
                args.profile.write_text(json.dumps(profile))
                with self.assertRaisesRegex(ValueError, "finite.*X"):
                    PREP.validate_args(args, int(time.time() * 1000))

    def test_inconsistent_carryover_accounting_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = self.fixture(temporary)
            carry = json.loads(args.carryover.read_text())
            carry["verifiedPrimeDegrees"] += 1
            args.carryover.write_text(json.dumps(carry))
            with self.assertRaisesRegex(ValueError, "accounting fields disagree"):
                PREP.validate_args(args, int(time.time() * 1000))


if __name__ == "__main__":
    unittest.main()
