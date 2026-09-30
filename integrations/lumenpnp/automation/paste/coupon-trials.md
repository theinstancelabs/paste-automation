# Offline scrap-pad dose trials

This planner supports the [commissioning strategy](commissioning-strategy.md): run a **screening comparison** on distinct pads of the unplatformed scrap on the +Y side of the demo, then validate repeatability before considering the demo. It issues no G-code, controller connection, motion or current changes, and never enables the existing air/wet paths. CAD/video values and the phrase “+Y of demo” do not supply registered targets, surface Z or clearance.

`coupon-request.pending.json` deliberately has an empty pad list and unmeasured fields. Keep it empty until actual pads are identified and registered. It is a valid preparation template, not a runnable plan. Work on private copies; do not fill repository templates with machine calibration.

## Comparison preparation

Supply the calibrated native profile accepted by `safety.cjs`, retaining its measurement/configuration references. The CLI records the exact profile-file SHA-256 plus profile snapshot. The request needs:

- Measured scrap bounds and demo exclusion bounds in `openpnp-N2-mm`, minimum separation on +Y, scrap registration/surface/clearance records, and actual tip/material identification. The unplatformed scrap surface must be measured independently of the raised demo.
- Exactly six unique unused pads of matching rectangular extents. Each pad has `id`, `unused: true`, explicit registered `x`/`y`, independently established `surfaceZ`, and `extents` with `xMin`, `xMax`, `yMin`, `yMax`. Pads 1–3 compare doses; 4–6 are reserved for repeats. Use separate requests for materially different pad sizes.
- Measured minimum pad edge-to-edge spacing and tip edge margin. Entire pad rectangles must lie on the scrap and inside native bounds. Geometry checks do not establish actual paste spread, physical obstacles, or safe travel between pads.
- Three explicitly reviewed positive doses, strictly increasing and below the documented dose ceiling. No guessed default is generated. Keep retraction, dwell, standoff, observed motor current, dispense angular rate and retraction angular rate fixed across all three trials. Record the observed current/settings source and explicit maximum current/rates with their review record; all requested values are bounded before a plan is emitted. These are trial parameters, not executable native B commands.
- A remaining gross stroke budget for these deposits after separately accounting for priming and prior activity. Retraction does not replenish the planner's gross budget. Any extra priming/retry/uncertain stroke consumption needs a new physical accounting and review.

```sh
node automation/paste/coupon-trials.mjs compare request.json measured-profile.json comparison.json
```

The output is deterministic for identical inputs, has three labeled trials and three reserved pad IDs, and refuses to overwrite an existing file. Dose 1/2/3 are assigned to pads 1/2/3 in their supplied order. This small screening comparison therefore confounds dose with pad position; it is not a controlled dose-response estimate or calibration. Later work needs genuine replication across positions before drawing a process conclusion. It includes no machine execution instructions. Every output retains `executionEnabled: false`, `physicalAcceptanceEstablished: false` and `demoAuthorized: false`.

## Actual observations

After a separately authorized and supervised physical trial, write an observation JSON containing:

- `planSha256`, `trialId`, `padId`, `operator`, UTC `observedAt`, and descriptive `notes`.
- `outcome`: `deposited`, `no-deposit`, `uncertain`, or `not-run`.
- `assessment`: `too-small`, `too-large`, `acceptable-by-operator`, `defective`, or `unassessed`. Only a deposited result may be labeled acceptable by the operator; this label is not software acceptance.
- Actual `appliedDoseDegrees`, `appliedMotorCurrentMa`, `appliedDispenseDegreesPerMinute`, `appliedRetractionDegreesPerMinute`, and boolean `settingsMatchedPlan`. Current and both rates are required for deposited/no-deposit trials; a true match claim is checked against each planned value. Actual dose may be null only for uncertain/not-run outcomes. Recording a discrepancy is permitted, but it blocks repeat planning. Do not infer physical deposition from software completion.
- `evidence`: references with absolute `path` and file `sha256`; required for observed/uncertain trials. `settingsEvidence`: references with absolute path and SHA-256 of the actual motor-current/rate setting record; required for deposited/no-deposit trials. `measurements`: an array of actual entries with `name`, nonnegative `value`, `unit` (`mm`, `mm2`, `ms`, `count`) and `method`; an empty array is allowed when no quantitative measurements were taken.

```sh
node automation/paste/coupon-trials.mjs record comparison.json observation.json observation-record.json
```

The CLI verifies the profile and evidence file hashes, preserves the observation, binds it to the exact plan/trial/pad and refuses overwrite. Evidence hashes establish file identity, not that an image proves a good deposit. Review coverage, centering, bridges/spread, tail/stringing, missed/delayed flow and contamination as physical observations.

## Separate repeat validation

Collect the three immutable comparison records in a JSON array. Supply a separate selection JSON with `comparisonSha256`, `selectedTrialId`, `operator`, UTC `reviewedAt` after the observations, `reason`, `evidenceRecord`, and explicit `fixtureUnchanged: true` / `registrationCurrent: true` attestations. These are operator claims, not automated live-state checks. Re-register and start a newly reviewed plan if the scrap, head, syringe/tip, fixture or registration changed.

```sh
node automation/paste/coupon-trials.mjs repeat comparison.json records-array.json selection.json repeats.json
```

All three screening results must be accounted for with matching actual dose, current and angular rates; uncertainty or an unrun result blocks repeat planning. The selected dose requires the operator's explicit acceptable-deposit assessment. The output repeats that one dose on the three reserved unused pads, retaining the other parameters and capping comparison-plus-repeat gross stroke. Duplicate trial records cannot satisfy this gate. No trial is automatically replayed.

Record each repeat against `repeats.json` using the same `record` command. There is no automatic winner, aggregate pass, calibration promotion or authorization to paste the demo. An operator must review actual consistency and all commissioning gates separately. The software tests use synthetic numbers only:

```sh
node --test automation/paste/coupon-trials.test.cjs
```
