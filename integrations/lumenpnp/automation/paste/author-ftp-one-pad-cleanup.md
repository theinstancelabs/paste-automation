# Author one-pad cleanup inputs offline

```sh
python3 automation/paste/author-ftp-one-pad-cleanup.py --inputs REVIEWED.json --output NEW_DIRECTORY
```

Fill `author-ftp-one-pad-cleanup.inputs.example.json` with the actual reviewer/time, review text, explicit attestations, current hash-bound sources and full barrier raw pose. The barrier must already be at the selected clearance. Select exactly one eligible defect (R1.1, R40.1 or R16.2), positive retraction6 or20, and integer dwell0..2000. `defectCapturedMs` must equal the fresh camera report finish time; that report must bind the selected image and session. Fresh tip/stationary images must precede the authored review. This wrapper obtains no observations, renews no evidence timestamps, and makes no automatic physical attestations.

The wrapper preserves the accepted registration/revalidation, distant-pad checks and CAD evidence from `targetBase`, and replaces dispensing-specific fields with the explicit cleanup target. It derives quantized XY from registered coordinates minus the bound tip offset. Surface evidence supplies the selected working Z and provisional gap; the starting clearance profile gap is that gap plus the work-to-clearance difference. Neither is promoted to calibrated height or flow. Source bytes are hash-checked before and after calling the existing disabled cleanup preparer, which retains all positive-only, one-pad, immediate-lift, 40-stage, native-preview and ledger gates. Existing output directories are refused. Result: `prepared/native/preview-request.json`; no preview or motion is dispatched.

The cleanup terminal and charged ledger must become the exact prior evidence for any later B action. A +20 cleanup after the ordinary final+40 relief leaves +60 degrees of cumulative relief. The standard prime−60 and pre-wipe+20 net−40, leaving +20 more relief than the ordinary starting state. The conditioner and matched restores do not erase that difference; motor arithmetic does not establish pressure or flow.

The simplest workflow is to finish dispensing before defect cleanup, avoiding another dispensing restart. If dispensing must resume afterward, keep the existing amounts and budget and perform a freshly reviewed conditioning trial on scrap before relying on transfer again. Do not silently add prime80, an extra forward stroke, a ledger refund, or a larger budget to compensate. Cleanup is an experimental positive-B action; actual aspiration/removal and subsequent flow remain subject to fresh image review.
