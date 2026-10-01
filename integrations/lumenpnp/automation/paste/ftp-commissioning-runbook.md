# FTP paste commissioning checkpoint and saved workflow

At the October 1 selected-six checkpoint, parent image review found visible paste on all 80 resistor pads. This is coverage, not physical acceptance. Paste volume, height accuracy, reflow performance and production repeatability remain unverified.

| Unresolved pad | Observed issue |
| --- | --- |
| R1.1 | Oversized deposit |
| R40.1 | Oversized deposit |
| R16.2 | Long residue string from the earlier group |
| R40.2 | New tail after the selected-six trial |

The sole selected-six wet request was `8c85165f-35f3-4a7c-8ff9-b45570b896d8`, completed at 15:14:59.870 UTC with 79 verified stages and no uncertain completion. It dosed R3.1, R3.2, R2.1, R2.2, R1.2 and R40.2, charging 246 gross degrees. The checkpoint ledger total was 7369 degrees and B was −2889. Follow-up camera reports were R40 `03c831bb`, R1 `b8c4f9bc`, R2 `4e2bb30e`, and R3 `2063e427`, captured at 15:15–15:16 UTC. These reports and the private image review support the final coverage observation; command completion alone does not prove deposit quality.

## Last executed recipe

This records the experiment, not a calibrated dispensing recommendation. Working heights were supplied by individually reviewed provisional surface evidence: 58.37 for R3, 58.36 for R2, 58.35 for R1.2 and 58.29 for R40.2 in this machine's raw coordinates. Do not reuse these values for another setup or infer a precision gap from them.

1. Prime 60 degrees using three −20 strokes, waiting 2000 ms after the last. Relieve +20, wait 1000 ms, perform the explicitly reviewed initial scrap wipe, and lift to the reviewed clearance.
2. At the fresh dummy point, restore −3, dose −6 then −6, wait 2000 ms after the second, retract +3, wait 500 ms, and lift. Final dummy wipe is zero.
3. Transit at the reviewed common clearance. The first FTP restore must start within 15 seconds of the verified conditioning retraction; its wait and transit consume that time.
4. At each reviewed pad, restore −3, dose −6 then −6, wait 2000 ms, retract +3, wait 500 ms, then immediately lift. XY travel stays at clearance. Each pad retains its own reviewed surface evidence.
5. After the last lift, relieve +20 then +20, waiting 2000 ms after the second. B uses the existing 0.05 speed fraction; XYZ uses 1.0. Native per-stage limits, exact formatter traces, position/count checks and full gross ledger charging remain required.

## Reusable saved workflow

Prepare actual reviewed input JSON for `author-conditioned-ftp-selected-pads.py`. Supply explicit reviewer/time and attestations; hash-bound registration and valid revalidation; fresh pad report/image pairs; individual surface records; current barrier, ledger and previous wet terminal; fresh stationary/tip images; and reviewed scrap points and clearance. The author does not obtain observations or create physical attestations. Selected scope supports one to eight unique pads, at most 96 stages, and one uninterrupted conditioning/transfer route.

```sh
python3 automation/paste/author-conditioned-ftp-selected-pads.py --inputs REVIEWED.json --output NEW_DIRECTORY
python3 automation/paste/run-prepared-contiguous-batch.py --prepared-dir NEW_DIRECTORY/prepared/native --preview
python3 automation/paste/run-prepared-contiguous-batch.py --prepared-dir NEW_DIRECTORY/prepared/native --execute
```

The first command creates disabled artifacts only. Preview uses the existing owner's model-only formatter. Execute finalizes the matching preview and uses the reviewed existing controller owner. Inspect the generated request before execution; retain its ID and actual report path. The runner creates a durable attempt receipt and observes an existing same-ID attempt/report instead of dispatching again. Selected/eight-pad terminal polling is 300 seconds. A timeout or uncertain outcome is not permission to replay: inspect that same report and use the established reviewed recovery path if necessary. Camera inspection and an updated coverage/defect assessment follow each physical trial.

Do not extend expired evidence by changing timestamps. Pad availability and setup reviews remain subject to their five-minute gates. A registration revalidation has its own one-hour window with original evidence preserved. The private executed-helper archive is historical evidence, not a reusable source of fresh attestations.

## Cleanup and pressure history

The existing cleanup author permits exactly one reviewed R1.1, R40.1 or R16.2 defect, one positive +6 or +20 B action, and immediate clearance lift. It requires a fresh defect camera report/image and current registration, tip, surface and clearance evidence. Positive B is an experimental aspiration attempt; it does not prove paste removal. R40.2 is not admitted by the current cleanup scope.

After ordinary final +40 relief, a +20 cleanup leaves +60 cumulative relief. Standard prime −60 followed by pre-wipe +20 nets −40, retaining +20 more relief than the ordinary starting state. Matched dummy restore/dose/retract commands do not erase that difference or establish pressure. Finish deposition before cleanup where possible; any dispensing restart requires fresh reviewed scrap conditioning with the charged history retained. Do not silently increase prime, add a forward stroke, refund ledger charge, or reuse a pre-cleanup terminal.

A separate earlier observation showed a new scrap deposit across approach, about seven minutes of idle and lift with B unchanged. Passive ooze or transfer of carried tip residue are both compatible; neither a continuous flow rate nor the exclusive cause was measured. Keep this limitation in the physical review.
