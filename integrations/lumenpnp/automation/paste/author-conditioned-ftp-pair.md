# Offline conditioned FTP pair authoring

Run `python3 automation/paste/author-conditioned-ftp-pair.py --inputs REVIEWED.json --output NEW_DIRECTORY`.

Start from `author-conditioned-ftp-pair.inputs.example.json`. Supply an actual authored `reviewedMs`, reviewer, review/profile text, explicit true physical attestations, exact barrier `startRaw`, selected surface/clearance Z, two scrap targets and SHA-256 evidence references. `pairReviews` contains exactly one resistor with both pad IDs in the requested order; its identity/availability review and camera capture timestamp are explicit inputs. No observation or timestamp is generated on the reviewer's behalf.

The existing pair dose choices are 2, 3, 4, 6, 12 and 20 degrees. Forward dwell is an explicit integer from 0 through 2000 ms (default 200), matching the existing pair policy; restore/retract is explicitly 2 or 3 degrees (default 2), retract wait 500 ms and final relief 40 degrees. The supplied transfer-preparation experiment retains its conditioner amounts and timing. A 12-degree dose is expanded by the existing pair preparer into two −6 stages, with the forward wait on the last.

The author derives quantized head XY from the accepted registration minus the selected tip offset, writes new records, then invokes `prepare-conditioned-ftp-pair.py` and its disabled generic validator. It preserves source bytes, checks every supplied source hash before and after preparation, refuses existing output directories, and surfaces validator errors. Output is `prepared/native/preview-request.json`, disabled and not dispatched. Native preview/finalization, motion, physical review, registration freshness and the unchanged 40-stage cap remain separate existing gates. This helper makes no calibration or transfer-quality claim.

Optional author input `retractDegrees` accepts integer 2 or 3, defaulting to 2. The selected value is copied into both the transfer conditioner and every FTP restore/retract. Retract wait stays 500 ms and final relief stays 40 degrees. A standard eight-pad 12-degree/R3 recipe charges 287 gross degrees with net −113.
