# FTP paste commissioning checkpoint and saved workflow

## Current continuation — 2026-10-01

The first fresh eight-pad batch, `e23c7a5d-eb2b-4b75-a0e6-bdbb028f5f19`, ran 19:27:20.941–19:28:42.385 UTC for R36, R35, R34 and R33. It completed 76/76 verified stages; final raw pose was X315.09, Y235.32, Z53.45, A720, B−3033, with charged ledger 8503 degrees. The preliminary image review called these deposits compact, but later dimensional inspection estimates about 0.9–1.4 mm on 0.8×0.95 mm pads. Withdraw that acceptance: the eight deposits are oversized and not accepted.

The R37–R40 group also deposited, but the smaller footprints and tails were not accepted. R32/R31 and R30.1 had partial deposits; R30.1 became oversized after dwell. A separate R29/R2 dose12 trial produced two similar roughly 0.6–0.7 mm 2D footprints, a size candidate only, not a qualified recipe. A six-pad R28/R27/R26 batch (`4517dee0-21f5-401b-a7f4-8844591cbfad`) completed and is awaiting image review; do not infer its quality yet.

The third group stopped under request `9d2592a4-0b68-41a7-ba1a-4fa1e7b40bc9` after 52 verified stages at raw X321.04, Y213.07, Z58.25, A720, B−3174. A fresh audit completed; no collision was observed. The reconciled ledger retained the full reservation. A later +40-degree wet stroke completed and advanced the charged ledger to 9007 degrees, B−3134, validating the reservation/reconciliation runtime path only. It does not qualify any deposit.

Fresh native fiducial registration refresh 2 was accepted at 19:34 UTC. Current review remains open: prior group dimensions and tails are not accepted, the six-pad after-images are pending, and total-board completion is not established. Continue to inspect each group and preserve the full charged history.

The earlier all-80 coverage/cleanup checkpoint below is historical and superseded as current-state guidance. Do not use it to infer present board condition or to issue a cleanup directive.

The following table and records describe the prior inspection and cleanup history, not current pad state.

| Unresolved pad | Observed issue |
| --- | --- |
| R1.1 | Oversized deposit |
| R40.1 | Oversized deposit and loop bridge to R40.2, present before the first cleanup trial |
| R16.2 | Long residue string from the earlier group |
| R40.2 | Tail after the selected-six trial; subsequently observed loop bridge to R40.1 |
| R7.1, R11.1, R15.1, R23.1 | First-deposit edge residue or tails |
| R34.1 | Off-center deposit near the pad edge |
| R30.1, R31.1, R32.1 | Long strings observed in the fresh inspection |
| R37.2, R39.2 | Tails |
| R19.1 | Extra residue |
| R3.1; R2 | Oversized R3.1 deposit; large R2 deposits |
| R30.2, R31.2, R32.2, R33.1, R35–R38 | Small or variable footprints |

The prior fresh images did not establish when the newly observed strings formed. Their associated whole-board wipe request is superseded by the new registration and continuing deposition sequence above. Treat the listed issues as historical observations only; inspect current images before deciding whether any cleanup is needed.

The earlier selected-six wet request was `8c85165f-35f3-4a7c-8ff9-b45570b896d8`, completed at 15:14:59.870 UTC with 79 verified stages and no uncertain completion. It dosed R3.1, R3.2, R2.1, R2.2, R1.2 and R40.2, charging 246 gross degrees. The checkpoint ledger total was 7369 degrees and B was −2889. Follow-up camera reports were R40 `03c831bb`, R1 `b8c4f9bc`, R2 `4e2bb30e`, and R3 `2063e427`, captured at 15:15–15:16 UTC. These reports and the private image review supported the earlier coverage observation; command completion alone does not prove deposit quality.

## Last executed recipe

This records the experiment, not a calibrated dispensing recommendation. Working heights were supplied by individually reviewed provisional surface evidence: 58.37 for R3, 58.36 for R2, 58.35 for R1.2 and 58.29 for R40.2 in this machine's raw coordinates. Do not reuse these values for another setup or infer a precision gap from them.

1. Prime 60 degrees using three −20 strokes, waiting 2000 ms after the last. Relieve +20, wait 1000 ms, perform the explicitly reviewed initial scrap wipe, and lift to the reviewed clearance.
2. At the fresh dummy point, restore −3, dose −6 then −6, wait 2000 ms after the second, retract +3, wait 500 ms, and lift. Final dummy wipe is zero.
3. Transit at the reviewed common clearance. The first FTP restore must start within 15 seconds of the verified conditioning retraction; its wait and transit consume that time.
4. At each reviewed pad, restore −3, dose −6 then −6, wait 2000 ms, retract +3, wait 500 ms, then immediately lift. XY travel stays at clearance. Each pad retains its own reviewed surface evidence.
5. After the last lift, relieve +20 then +20, waiting 2000 ms after the second. B uses the existing 0.05 speed fraction; XYZ uses 1.0. Native per-stage limits, exact formatter traces, position/count checks and full gross ledger charging remain required.

## Reusable saved workflow

Prepare actual reviewed input JSON for `author-conditioned-ftp-selected-pads.py`. Supply explicit reviewer/time and attestations; hash-bound registration and valid revalidation; fresh pad report/image pairs; individual surface records; current barrier, ledger and previous wet terminal; fresh stationary/tip images; and reviewed scrap points and clearance. The author does not obtain observations or create physical attestations. The existing selected scope supports one to eight unique pads and at most 96 stages. For a single larger route, use the separate input scope `reviewed-selected-pads-up-to-40-authoring-inputs`; it supports up to 40 unique pads and at most 400 stages. Both retain the same per-pad evidence, axis-step, clearance, fresh-session, native preview, and B-ledger limits.

```sh
python3 automation/paste/author-conditioned-ftp-selected-pads.py --inputs REVIEWED.json --output NEW_DIRECTORY
python3 automation/paste/run-prepared-contiguous-batch.py --prepared-dir NEW_DIRECTORY/prepared/native --preview
python3 automation/paste/run-prepared-contiguous-batch.py --prepared-dir NEW_DIRECTORY/prepared/native --execute
```

The first command creates disabled artifacts only. Preview uses the existing owner's model-only formatter. Execute finalizes the matching preview and uses the reviewed existing controller owner. Inspect the generated request before execution; retain its ID and actual report path. The runner creates a durable attempt receipt and observes an existing same-ID attempt/report instead of dispatching again. Selected/eight-pad terminal polling is 300 seconds. A timeout or uncertain outcome is not permission to replay: inspect that same report and use the established reviewed recovery path if necessary. Camera inspection and an updated coverage/defect assessment follow each physical trial.

Do not extend expired evidence by changing timestamps. Pad availability and setup reviews remain subject to their five-minute gates. A registration revalidation has its own one-hour window with original evidence preserved. The private executed-helper archive is historical evidence, not a reusable source of fresh attestations.

## Cleanup and pressure history

Further aspiration trials were abandoned after both +20 and +100 produced no useful removal. The earlier R1/R16/R40 rework request has been superseded by the whole-board wipe request above; physical rework remains unresolved. The stored cleanup tools below describe historical experimental capability, not a recommended continuation of this failed method.

The existing cleanup author permits exactly one reviewed R1.1, R40.1 or R16.2 defect, one positive +6 or +20 B action, or an explicitly selected 100-degree series of five consecutive +20 stages, followed by immediate clearance lift. The 100-degree protocol allows at most 2000 ms after each stage, no interleaved motion and no forward B; it charges all 100 gross degrees and preserves the original 40-stage route cap. It requires a fresh defect camera report/image and current registration, tip, surface and clearance evidence. Positive B is an experimental aspiration attempt; it does not prove paste removal. R40.2 is not admitted by the current cleanup scope.

After ordinary final +40 relief, a +20 cleanup leaves +60 cumulative relief. Standard prime −60 followed by pre-wipe +20 nets −40, retaining +20 more relief than the ordinary starting state. Matched dummy restore/dose/retract commands do not erase that difference or establish pressure. Finish deposition before cleanup where possible; any dispensing restart requires fresh reviewed scrap conditioning with the charged history retained. Do not silently increase prime, add a forward stroke, refund ledger charge, or reuse a pre-cleanup terminal.

A separate earlier observation showed a new scrap deposit across approach, about seven minutes of idle and lift with B unchanged. Passive ooze or transfer of carried tip residue are both compatible; neither a continuous flow rate nor the exclusive cause was measured. Keep this limitation in the physical review.

The first R40.1 cleanup (`0d9d1533`) completed +20 with a 2000 ms wait at work Z58.29, reaching B=−2869 and total charged history7389. Inspection `b1167f55` showed no meaningful removal. Fresh before-image `845101fb` already showed a loop bridge from R40.1 to R40.2; it was not first created by the +20 trial. The parent identified carried long-strand residue during the earlier approach as the concern, and used a separate no-B scrap wipe before that +20 cleanup attempt. The immutable original review basis is retained alongside a private observation supplement. The subsequent +100 trial was an explicit experiment; it did not establish a working cleanup method or measured 5.8 µL removal.

## Saved no-B scrap wipe

The observed no-B wipe `a0345e39-e4bf-43a8-9760-3945284a3ef7` finished at 15:26:51.326 UTC, before the +20 R40 cleanup. It approached the reviewed scrap work height, moved +X1.5 mm and lifted, with B remaining −2889. The retained private tip-after image (`cleanup-scrap-wipe1-tip-after/frame-11.jpg`) and parent review supported removal of the long strand in this single trial. They do not establish a residue-free tip, repeated cleaning reliability, or freedom from later ooze.

`author-no-b-scrap-wipe.py --inputs REVIEWED.json --output NEW_DIRECTORY` saves this class of explicitly reviewed scrap-only route through the existing disabled air pipeline. It requires a current barrier at clearance, source hashes, fresh image and explicit tip/path review, provisional gap bounds, and one X/Y wipe of at most 2 mm; it generates no B stage and performs no camera, vacuum, homing or dispatch action. See `author-no-b-scrap-wipe.md` for exact inputs. Use the emitted preview request’s parent directory with the existing prepared runner for separately reviewed preview/execution.

The +100 trial `03beac0c` completed at 15:38:43.195 UTC with B=−2769 and total charged history 7489. After-image `155ffa17` at 15:39:42.869 still showed the R40 loop bridge; the blob was more lobed, without useful removal. No additional aspiration is planned. The historical crop review also identified variable/small early R30–R38 deposits, R34.1 off-center paste, and first-deposit edge/tail residue on R7.1, R11.1, R15.1 and R23.1. These findings prevent a uniform-deposition or physical-acceptance claim. Scrap repeatability work continues independently; the board is not declared finished.

## Two dose6 scrap repeats after board deposition

These ordinary scrap coupons are separate from the FTP dose12 recipe recorded above. Both used prime60 (three −20 stages; 2000 ms after the last), pre-wipe relief +20/1000 ms and the reviewed initial scrap wipe; conditioner −6/2000 ms then +3/500 ms and lift; three test deposits each with restore −3, dose −6/2000 ms, retract +3/500 ms and lift; final relief +20 then +20/2000 ms at clearance. There was no initial dummy restore or final dummy wipe. B speed remained 0.05 and XYZ speed 1.0. Raw work Z58.45 and clearance53.45 were this session’s provisional geometry, not measured gap calibration or reusable setup values.

| Trial | Wet report | Actual controller elapsed | Accounting | Parent image review |
| --- | --- | --- | --- | --- |
| Coupon3 | `2561fbf8` | 48.460 s (16:16:00.898–16:16:49.358 UTC) | 31 stages; gross165, net−21 | After `c7170d7b`: three compact/roundish, separate dots, about 70–85 pixels (~0.8–0.9 mm at approximately 91 pixels/mm); irregular dummy excluded. |
| Coupon4, exact parameter repeat | `b184d0e7` | 48.464 s (16:21:40.747–16:22:29.211 UTC) | 31 stages; gross165, net−21 | After `64d095ba`: three compact separate roundish dots, about 55–70 pixels, slightly smaller than coupon3; no obvious long string. |

The two rows showed six visible transfers, with size variation between repeats. These are coarse 2D footprint observations, not deposited-volume, reflow or production-repeatability qualification. Bare-mask coupon transfer does not establish that dose6 is optimal on FTP copper. The canonical `prepare-retraction-coupon.py` can reproduce this command structure using explicit conditioner6, dose6, retract3 and the stated waits, with fresh reviewed targets, source hashes, profile and ledger evidence; it does not create physical attestations.

After coupon4, charged history was 8278 degrees of 8400 and B was −2982; no charge was refunded. At that coupon checkpoint, manual R1/R16/R40 rework remained pending. The later fresh whole-board inspection and expanded cleanup request are recorded above; these scrap results do not qualify FTP deposition.

## Parked state and resumption conditions

The later canonical no-B scrap wipe `669e22da` completed at 16:27:18.262 UTC. It moved X307.48→308.98 at Y301.32 and raw Z58.45, then lifted to 53.45, with B remaining −2982. Parent review of the fresh 4K after-image showed the hanging blob removed; it does not prove a residue-free tip or reliable subsequent cleaning.

Final park `552ab483` completed at 16:35:41.805 UTC at raw X294.98, Y298.82, Z32.25, A720, B−2982. No motion was queued at this checkpoint. Charged history was 8278 of 8400 degrees, leaving 122 degrees. A full dispensing batch exceeds this remaining allowance. Review actual remaining mechanical travel before increasing the cap; do not reset or refund the ledger. No additional B motion is planned while PCB cleanup is pending.

Revalidation6 centroid errors were FID1: 0.727 pixels (pass), FID2: 3.658 pixels (fail), and FID3: 3.816 pixels (fail). There is no newly accepted revalidation and no affine-registration change. After the requested whole-board cleanup, inspect actual board condition and movement and obtain a fresh accepted registration check before deposition. Do not reuse failed checks or freshen old timestamps.
