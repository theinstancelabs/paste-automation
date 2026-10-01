# Prepare a paste dose cycle

`prepare-dose-cycle.py` validates source report, reviewed image, receiving profile, prior report, and syringe-ledger inputs. The default command only prints a preliminary validation summary; it does not create plans, query OpenPnP, or claim that the native request builder passed.

Pass `--prepare-native` to create a fresh read-only position barrier and disconnected three-stage formatter preview, then build a disabled cycle request under the requested output directory. This mode still does not dispatch the B dose, retract, or Z lift. Execution remains a separate reviewed action.

```sh
python3 automation/paste/prepare-dose-cycle.py \
  --source /path/to/current-terminal-report.json \
  --image /path/to/fresh-reviewed-image.png \
  --profile /path/to/current-receiving-profile.json \
  --previous-report /path/to/previous-stroke-or-cycle-report.json \
  --prime-ledger /path/to/current-prime-ledger.json \
  --prior-ledger /path/to/prior-session-ledger.json \
  --carryover /path/to/hash-bound-carryover.json \
  --dose 4 --retract 2 --dwell 200 \
  --review "reviewed clean scrap pose and lift corridor" \
  --output-dir /path/to/new-cycle-evidence
```

Add `--prepare-native` only when ready to run the read-only barrier and disconnected preview. The previous report supplies the shared commissioning-ledger path. The existing offline cycle builder performs the final request and policy validation.
