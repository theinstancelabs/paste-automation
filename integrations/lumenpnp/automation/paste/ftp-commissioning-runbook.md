# FTP paste commissioning checkpoint and saved workflow

Parent review of the historical 80-pad crop gallery found visible paste on all 80 resistor pads. These were retained post-deposition frames, not a new simultaneous whole-board inspection. This is coverage, not physical acceptance. Paste volume, height accuracy, reflow performance and production repeatability remain unverified.

| Unresolved pad | Observed issue |
| --- | --- |
| R1.1 | Oversized deposit |
| R40.1 | Oversized deposit and loop bridge to R40.2, present before the first cleanup trial |
| R16.2 | Long residue string from the earlier group |
| R40.2 | Tail after the selected-six trial; subsequently observed loop bridge to R40.1 |
| R7.1, R11.1, R15.1, R23.1 | First-deposit edge residue or tails |
| R34.1 | Off-center deposit near the pad edge |
| Earlier R30–R38 trials | Several very small or variable footprints; see historical crop review |

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

Further aspiration trials were abandoned after both +20 and +100 produced no useful removal. Physical rework of R1, R16 and R40 has been requested and remains unresolved. The stored cleanup tools below describe historical experimental capability, not a recommended continuation of this failed method.

The existing cleanup author permits exactly one reviewed R1.1, R40.1 or R16.2 defect, one positive +6 or +20 B action, or an explicitly selected 100-degree series of five consecutive +20 stages, followed by immediate clearance lift. The 100-degree protocol allows at most 2000 ms after each stage, no interleaved motion and no forward B; it charges all 100 gross degrees and preserves the original 40-stage route cap. It requires a fresh defect camera report/image and current registration, tip, surface and clearance evidence. Positive B is an experimental aspiration attempt; it does not prove paste removal. R40.2 is not admitted by the current cleanup scope.

After ordinary final +40 relief, a +20 cleanup leaves +60 cumulative relief. Standard prime −60 followed by pre-wipe +20 nets −40, retaining +20 more relief than the ordinary starting state. Matched dummy restore/dose/retract commands do not erase that difference or establish pressure. Finish deposition before cleanup where possible; any dispensing restart requires fresh reviewed scrap conditioning with the charged history retained. Do not silently increase prime, add a forward stroke, refund ledger charge, or reuse a pre-cleanup terminal.

A separate earlier observation showed a new scrap deposit across approach, about seven minutes of idle and lift with B unchanged. Passive ooze or transfer of carried tip residue are both compatible; neither a continuous flow rate nor the exclusive cause was measured. Keep this limitation in the physical review.

The first R40.1 cleanup (`0d9d1533`) completed +20 with a 2000 ms wait at work Z58.29, reaching B=−2869 and total charged history7389. Inspection `b1167f55` showed no meaningful removal. Fresh before-image `845101fb` already showed a loop bridge from R40.1 to R40.2; it was not first created by the +20 trial. The parent identified carried long-strand residue during the earlier approach as the concern, and used a separate no-B scrap wipe before that +20 cleanup attempt. The immutable original review basis is retained alongside a private observation supplement. The subsequent +100 trial was an explicit experiment; it did not establish a working cleanup method or measured 5.8 µL removal.

## Saved no-B scrap wipe

The observed no-B wipe `a0345e39-e4bf-43a8-9760-3945284a3ef7` finished at 15:26:51.326 UTC, before the +20 R40 cleanup. It approached the reviewed scrap work height, moved +X1.5 mm and lifted, with B remaining −2889. The retained private tip-after image (`cleanup-scrap-wipe1-tip-after/frame-11.jpg`) and parent review supported removal of the long strand in this single trial. They do not establish a residue-free tip, repeated cleaning reliability, or freedom from later ooze.

`author-no-b-scrap-wipe.py --inputs REVIEWED.json --output NEW_DIRECTORY` saves this class of explicitly reviewed scrap-only route through the existing disabled air pipeline. It requires a current barrier at clearance, source hashes, fresh image and explicit tip/path review, provisional gap bounds, and one X/Y wipe of at most 2 mm; it generates no B stage and performs no camera, vacuum, homing or dispatch action. See `author-no-b-scrap-wipe.md` for exact inputs. Use the emitted preview request’s parent directory with the existing prepared runner for separately reviewed preview/execution.

The +100 trial `03beac0c` completed at 15:38:43.195 UTC with B=−2769 and total charged history 7489. After-image `155ffa17` at 15:39:42.869 still showed the R40 loop bridge; the blob was more lobed, without useful removal. No additional aspiration is planned. The historical crop review also identified variable/small early R30–R38 deposits, R34.1 off-center paste, and first-deposit edge/tail residue on R7.1, R11.1, R15.1 and R23.1. These findings prevent a uniform-deposition or physical-acceptance claim. Scrap repeatability work continues independently; the board is not declared finished.
