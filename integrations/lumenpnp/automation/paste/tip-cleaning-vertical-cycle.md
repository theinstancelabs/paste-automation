# Vertical tip cleaning cycle

`tip-cleaning-vertical-cycle.py` prepares one vertical dip or blot cycle at the already-centered X/Y/A/B position. It commands Z only through `observe-z-step.py`; B and the other fixed axes are checked against the starting raw pose after each verified step. It never sweeps laterally below the target. Preview is the default.

The operator must supply a verified current source report, fresh PNG/JPEG camera evidence, an explicit reviewed target raw Z, an explicit clearance raw Z, and an explicit dwell from 0 through 10,000 ms. Raw Z ordering is enforced as `clearance <= current start < target`; clearance may equal the starting plane so the cycle can return to the same safe height. No station or machine coordinates are assumed. The CAD's nominal dimensions are part coordinates and do not supply these machine coordinates. The helper reads the current native Z soft-limit snapshot used by `observe-z-step.py` and rejects the whole plan if either endpoint crosses an enabled soft limit. Disabled limits and safe-zone values are not treated as travel bounds. The cycle is limited to two Z steps because each step uses both a 60-second barrier wait and a 60-second motion wait; the remaining image lifetime must cover that worst-case wait, dwell and a 15-second margin. Steps use the existing reviewed Z increment choices; sub-1 mm steps require the matching verified firmware evidence before any step is dispatched.

```sh
python3 automation/paste/tip-cleaning-vertical-cycle.py SOURCE_REPORT IMAGE \
  --mode dip --target-z RAW_TARGET --clearance-z RAW_CLEARANCE --dwell-ms DWELL_MS \
  --review 'Reviewed vertical path, target, and clearance'
```

After reviewing the complete preview, add `--execute`. For a blot, use `--mode blot` and the separately reviewed cloth-contact raw Z. A dip/blot run requires the dispenser pressure to be relieved first. It records each native report and dwell interval under a UUID run directory, has no retry or automatic recovery, and establishes no physical acceptance. A failure during immersion can leave the tip at its last verified position; handle the fault under direct operator supervision.
