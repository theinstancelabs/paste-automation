# LumenPnP native integration source mirror

The canonical working automation repository is `/home/lumen/lumenpnp`. This directory is a source-only mirror for review, versioned backups and collaboration in the writable paste fork. It does not replace that machine repository or deploy changes to OpenPnP. `export-manifest.json` records the exact allowlist, source paths and SHA-256 hashes; the original pinned planner checkout remains `/home/lumen/paste-automation` at `c497bfbef2f7347538966c129bf7ac7bdc2c1a0f`.

Included: offline native air-plan validation, disabled staged air execution, installation lock, N2 model quarantine, guarded connection inspection, capture-only measurement records, the existing reviewed local bridge, viewer/chat/outbox source and relevant tests. Also included are the narrowly scoped one-shot native +10 mm raw-X camera survey, offline request builder, exact-fault stationary audit/model-only release, and an offline image translation estimator. These source paths do not authorize general travel; each survey binds a fresh reviewed corridor, exact live pose, JVM and configuration digest. Audit/release scripts retain installation-specific evidence hashes as fail-closed source guards; their underlying private evidence is not exported. Physical paste execution remains code-disabled. Wet native execution is not implemented. No measured extruder profile or calibrated job is included; pending JSON files contain unmeasured/null fields and false attestations.

No evidence, live plans, OpenPnP XML/jobs, machine snapshots, private backups, credentials, viewer tokens, chat contents or captured images are exported. Hardware/software identifiers and installation paths in source are deliberate fail-closed guards for the audited installation, not portable calibration. Files retain their canonical layout and dependencies. The dispatcher references legacy placement scripts kept only in the actual machine repository; do not try to operate it from this mirror. Machine scripts use explicit canonical paths and must never be run casually from tests. The canonical operational/commissioning records stay local because they include actual machine observations.

Read [integration scope and gates](automation/paste/README.md), [measurement recorder](automation/paste/measurement-recorder.md), and the historical [independent review](automation/paste/independent-review.md). Relative links in mirrored documents to unexported operations files refer to the canonical repository. The historical September 25 review predates the [September 30 user-supplied transcript review](../../docs/VIDEO_NOTES.md); no audiovisual or correction-card review is claimed.

Offline checks on the original machine (from this directory):

```sh
node --test automation/paste/*.test.cjs
python3 -m unittest discover -s automation/tests
```

The pinned-planner tests explicitly read `/home/lumen/paste-automation`; they intentionally fail if its commit/source changes. Other machines need a separately reviewed path adaptation. Fork-wide checks remain `npm test` and `npm run build` from the fork root. None of these checks demonstrates physical clearance, successful extrusion or supervised commissioning. JavaScript machine scripts are compiled for syntax without evaluation during review.

Changes should be made and tested in the canonical repository, then exported with an explicit allowlist and refreshed hashes. Review both the source diff and exclusions before committing or pushing. Do not copy a whole machine repository or state directory into this mirror.
