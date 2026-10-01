# Explicit input authoring for eight-pad batches

`python3 automation/paste/author-conditioned-ftp-eight-pad.py --inputs REVIEWED.json --output NEW_DIRECTORY`

Start from `author-conditioned-ftp-eight-pad.inputs.example.json`. It is intentionally incomplete, with false physical attestations. A reviewer must supply every observation, boolean, evidence path/SHA-256, and the original `reviewedMs` timestamp. The tool never creates a barrier, image, physical review, registration revalidation, or timestamp. All source records remain unchanged; output is exclusive and disabled. There are no machine calls or live-pointer writes.

`sources` selects the immutable template, fresh start barrier, fresh stationary and tip images, original accepted registration, accepted no-refit revalidation, an existing FTP target base (CAD and held-out checks), scrap experiment/profile bases, selected board surface and tip-offset records, and current previous report/ledger. `surfaceRawZ` must equal the supplied surface record. `startRaw` must equal the barrier. The selected scrap experiment must already specify its work/clearance Z, prime/wipe/conditioning/retraction parameters and transfer-preparation mode; only explicit startRaw, doseDegrees and the two supplied scrap XY targets are substituted. The scrap profile's measured gap and uncertainty are retained, with the new authored profile basis and start pose.

Each of four `pairReviews` identifies a unique resistor, the ordered `.1`/`.2` pad IDs (either order), actual camera report/image evidence, and `capturedMs` equal to that report's finish time in epoch milliseconds. The reviewer explicitly attests pad identity and availability. Sources must precede the authored review and remain within five minutes; images can be shared when they visibly cover multiple reviewed pairs. The native policy independently rechecks report/image linkage, session and freshness.

The authoring helper derives pad XY from the accepted registration minus the explicitly selected tip offset, quantized to 0.01 mm, and writes experiment, complete-route clearance review, profile and target records. It then calls `prepare-conditioned-ftp-eight-pad.py`, which in turn runs the existing disabled generic validation. Its output includes `prepared/native/preview-request.json`. It does not run the native preview, finalize a runtime request or dispatch. An actual request still requires those existing parent-controlled steps and physical review; this helper makes no volume or height-calibration claim.

Optional input `dwellMilliseconds` accepts exactly integer 200, 1000 or 2000, defaulting to 200 when omitted. It selects only the eight FTP forward-dose waits. The supplied conditioning experiment and its waits are retained.

Dose 20 remains one existing −20 B stage per pad. The group-only cap is 96 stages; dose 12 uses exactly two −6 stages per pad with the selected wait only on the second. This admission does not establish deposited volume or physical qualification.

The 12-degree option adds eight stages versus a single-part dose. The complete route must still fit 96 stages; longer routes are rejected. No single −12 native command or stroke admission is added. Standard conditioning plus eight 12-degree pads charges 270 gross degrees.

Optional author input `retractDegrees` accepts integer 2 or 3, defaulting to 2. The selected value is copied into both the transfer conditioner and every FTP restore/retract. Retract wait stays 500 ms and final relief stays 40 degrees. A standard eight-pad 12-degree/R3 recipe charges 287 gross degrees with net −113.
