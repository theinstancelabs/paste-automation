# Reviewed constant-Z XY survey route

`run-survey-route.py` previews by default. It reuses the existing `paste-survey` native action for each step; it is not another controller or serial owner. Supply an explicitly reviewed full-corridor route spec based on `survey-route.pending.json`. No usable target coordinates or physical clearance are bundled.

Each ordered waypoint contains exactly `axis` (`X` or `Y`) and an absolute `targetMm`. The wrapper splits the path into single-axis steps of at most 9.9 mm, leaving margin below the native 10 mm limit for reporting precision. It rejects diagonals, zero-length waypoints, more than 32 steps and more than 240 mm total travel. Actual cumulative requested distance is checked as well as planned distance. Z/A/B and both heads' native Z/rotation remain fixed; JVM/configuration must remain unchanged.

Optional `capturePolicy` defaults to `all`, preserving before/after top and bottom frames plus contact sheets for every step. An explicitly reviewed `capturePolicy: "endpoints"` captures before-images only on the first step and after-images only on the last step. Intermediate frames and per-step contact sheets are omitted; each step still performs its existing fresh position checks, one-axis native move, completion check, and independent after-M114 verification. The route report records the selected policy and the per-request endpoint flags. This changes image overhead only; it does not relax motion, corridor-evidence, freshness, or state guards.

The source report is bound by SHA-256 and must be a verified successful XY survey, Z observation or read-only position barrier. A stop audit alone cannot start a route. The same fresh hashed image and actual file capture mtime cover the complete ordered corridor and every intermediate segment for both heads, syringe, tubing and nearby objects. The complete route expires five minutes after that image timestamp. Evidence is not refreshed per step to extend authorization. A preview is not visual verification or physical acceptance.

```sh
python3 automation/paste/run-survey-route.py /absolute/reviewed-route.json
# Only after explicit full-route physical review:
python3 automation/paste/run-survey-route.py /absolute/reviewed-route.json --execute
```

Execution claims one route UUID and an exclusive `flock` file under the private backup directory. Each bounded native request uses a new UUID and the exact previous verified terminal state. The wrapper waits for that request's matching successful report before issuing another step. Native before/after top and bottom images remain in each survey record; the route report links hashes and sources. An old canonical survey request is archived only when its exact matching report is verified complete. Unknown or unfinished requests are preserved and block execution.

Dispatcher failures, mismatched reports, changed state, expired evidence, timeouts and native faults stop the route immediately. There is no retry, latch release, automatic return or recovery command. A timeout can leave the last native task running; it does not prove the machine stopped. The route lock coordinates wrappers, not arbitrary manual/native UI actions; existing native state and ownership guards must still pass at each step. A completed route awaits image review and establishes no board registration or paste calibration by itself.
