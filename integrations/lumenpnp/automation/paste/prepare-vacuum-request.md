# Current-pose vacuum evidence requests

This offline helper writes a new request with exclusive creation. It never dispatches, opens a connection, changes a threshold or moves hardware. Use a newly verified terminal survey/Z/barrier report and a reviewed current PNG/JPEG. Both state and image must be within five minutes; image mtime is an operator-reviewed freshness proxy, not proof of camera capture time.

```
python3 automation/paste/prepare-vacuum-request.py baseline \
  --report CURRENT_REPORT --image CURRENT_IMAGE --operator OPERATOR --tip-id NT1 \
  --reviewed-empty-free-air-and-clearance --output NEW_BASELINE_REQUEST.json
```

The request collects20 samples per phase after2seconds settling. After the existing stationary recorder completes with normal OFF, inspect the actual distribution:

```
python3 automation/paste/prepare-vacuum-request.py summarize \
  --report NEW_BASELINE_REPORT --output NEW_DISTRIBUTION.json
```

The summary recomputes raw bytes, timings, counts, means, extrema, spread, sample standard deviation, half-stream means and histogram. It does not select contact thresholds or declare acceptance. Unstable or drifting streams require investigation and a separately justified contract review; do not widen thresholds automatically.

For a probe, collect the baseline at the final approach pose, then obtain a fresh stationary position barrier. Supply an explicit review JSON with:

- `scope: "explicit-current-stream-and-probe-envelope-review"`, `reviewed: true`, named `operator`, `reviewedMs`, and the actual baseline file's `baselineSha256`.
- `targetSurfaceIdentity`, `reviewRecord`, `jointInterval`, `nativeZConfiguration`, and complete `contract` matching the native pending schema. The empty mean comes from the new ON stream. No floor, surface, target or noise threshold is inferred.
- `stationaryEvidencePath`, `targetEvidencePath`, `jointEnvelopeEvidencePath`, plus each explicit physical attestation from the pending schema.

```
python3 automation/paste/prepare-vacuum-request.py probe \
  --barrier CURRENT_BARRIER --baseline CURRENT_BASELINE --review EXPLICIT_REVIEW \
  --operator OPERATOR --tip-id NT1 --output NEW_PROBE_REQUEST.json
```

Both native validators run before output. The probe reference binding requires complete20-sample OFF/ON streams,2second settling, normal OFF, same JVM/config/tip/pose, and evidence within five minutes. It recomputes the supplied summaries and binds the request mean to the actual stream. Current conservative spread≤1, fresh mean band±1.5 and pump response≥10 remain explicit native contract bounds; these are not established contact sensitivity. Existing fresh3-OFF/8-ON sampling inside the probe uses the same2second OFF/ON settling and must also pass before any Z step. A failed/stale historical report is never reused. Normal controlled-policy OFF handling remains unchanged.
