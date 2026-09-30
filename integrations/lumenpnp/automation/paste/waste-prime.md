# Disabled waste-only priming adapter

`Prime_Paste_Into_Waste.js` is staged with `PASTE_WASTE_PRIME_ENABLED=false` and is not registered in either dispatcher. `Observe_Paste_B.js` retains its separate minus-one-degree contract. No measured receiver, usable request, actual native rate trace, or physical success is supplied by these files.

Each reviewed request permits one absolute B-only target, current B minus20 degrees, through the existing native planner/driver. The request binds the exact five-axis state, native poses, current homing artifact, B configuration, measured receiver and needle identity, initial syringe displacement accounting, and expected expanded native command lines. The measured physical tip height minus receiving-surface height must agree with the measured gap; the full uncertainty interval must stay within the reviewed interval with a lower bound of at least1mm. All other raw axes remain fixed.

The fixed `automation/evidence/paste-waste-prime-session/ledger.json` directory prevents a new request/session UUID from silently resetting accounting. Before any controller query or movement, the adapter reserves and verifies the full20 degrees. Reservations sum actual degrees, including an explicitly charged prior direction-test ledger; total cannot exceed the profile ceiling or300 degrees. Pending/faulted entries remain charged and block continuation. There is no automatic ledger reset, refund, new syringe migration, pressure reversal, recovery move, or retry.

Each later request needs a hash-bound physical observation of the previous successful report and new outlet/receiver images. Only `no-visible-paste` or `emerging-not-consistent` permits continuation. Consistent paste, abnormal behavior, and ambiguous observations stop the sequence. Controller ACKs and droplet observations never establish delivered volume or calibrated flow.

The formatter helper constructs a detached native driver, machine, head, mountable and axes, copies the live minimum rates and immutable send-on-change cache values, and calls the installed native formatter with transport methods blocked/intercepted. It records exact expanded lines and requires a literal B target with positive bounded feed and optional bounded M204 acceleration. The live driver is never used to format by transmitting, and mutable native objects are not shared. Before/after checks retain live coordinates/configuration. Offline fixture results demonstrate the formatter mechanism, not the actual machine's reviewed rate.

Full fresh M114 responses require one five-axis position/count line followed by ACK, and no reset/error/resend/disconnect. Absolute B counts use the audited float32 multiplication and round-away-from-zero rule at4.44steps/unit; non-B controller counts must stay unchanged. Any different installed firmware rule or steps setting requires a separate review. A terminal ledger entry requires verified report/counts, after-images, unchanged final machine state/configuration, and a verified saved ledger write.

Offline checks, with no running-machine attachment or configuration loading:

```sh
node --test automation/paste/waste-prime.test.cjs
javac -cp '/opt/openpnp/lib/*' -d /tmp automation/scripts/java/CheckWastePrimePreview.java
java -cp '/tmp:/opt/openpnp/openpnp-gui-0.0.1-alpha-SNAPSHOT.jar:/opt/openpnp/lib/*' CheckWastePrimePreview /home/lumen/lumenpnp
```

The Java runner evaluates only the synthetic detached fixture. Machine scripts themselves receive compile-only review. Activation remains a separate reviewed step after measured receiver evidence, actual expanded-command review, firmware identity/settings verification, and physical clearance; this staged implementation does not authorize movement.

## Offline request preparation and later activation

The request builder accepts a completed copy of `waste-prime-builder.pending.json`. Fill paths and review fields only from actual evidence. It hashes every artifact, checks the measured profile and uncertainty, validates the prior observation and durable ledger, and calculates the prospective reservation without writing it. It does not dispatch or enable anything. Run it from the canonical repository.

1. Finish the separately reviewed B model configuration (`limitRotation=false`, `wrapAroundRotation=false`, `invertLinearRotational=true`, feed100, acceleration500, jerk2000). Preserve configuration evidence and the current home artifact. Verify installed firmware B steps/rounding. Establish the receiver's measured physical tip/surface heights and restrained identity, both-head clearance, needle identity, current XYZ/A pose, and initial syringe accounting. Do not substitute nozzle model offsets or the synthetic fixture.
2. Obtain a fresh read-only position barrier at that exact pose. For the model-only formatter request, only `barrierPath` is needed in the input JSON:

   ```sh
   node automation/scripts/build_waste_prime_request.cjs --preview-only /absolute/path/to/reviewed-input.json automation/plans/paste-waste-prime-preview-request.json
   ```

3. After independent source review, the parent may register **only** `paste-waste-prime-preview` → `Preview_Paste_Waste_Prime.js` in the canonical JS action map and both JS/Python installation action allowlists/Python action list. It needs no busy exception and must not enable the wet adapter. The corresponding one-shot invocation is:

   ```sh
   python3 automation/scripts/run_reviewed_action.py paste-waste-prime-preview --confirmed
   ```

   Review the resulting `paste-waste-prime-preview-<UUID>/report.json`, including its literal B-only target, minimum-rate clamp, send-on-change behavior, and expanded command lines. This is current-model evidence, unlike the synthetic test. A changed pose/configuration or a trace older than five minutes requires a new preview. No controller command is sent by this script.
4. Populate `nativePreviewPath` and all remaining measured input paths. For the first increment the ledger and observation paths are explicitly null; an existing fixed ledger directory prevents a new start. For continuation use the exact canonical ledger path and a new hash-bound outlet/receiver observation of the previous terminal report. Generate the single wet request:

   ```sh
   node automation/scripts/build_waste_prime_request.cjs /absolute/path/to/reviewed-input.json automation/plans/paste-waste-prime-request.json
   ```

5. Review the concrete request, full measured profile, actual preview, and prospective total. Only after separate physical/transport authorization may the parent change `PASTE_WASTE_PRIME_ENABLED` to true and register `paste-waste-prime` → `Prime_Paste_Into_Waste.js` in the same canonical allowlists, without a busy exception. Neither registration nor that gate change has been made here. Its later one-shot invocation would be:

   ```sh
   python3 automation/scripts/run_reviewed_action.py paste-waste-prime --confirmed
   ```

6. Inspect the specific terminal report and fresh outlet/receiver imagery before any next request. Do not automatically rerun a dispatch after consumption, timeout, or uncertainty. A failed or pending reservation stays charged; consistent paste ends priming. No tool in this preparation sequence clears the durable ledger.

The builder atomically claims a new output JSON after validation and refuses an existing destination. Preserve/review a previous request before deliberately moving it aside; never infer that an old request is safe to repeat. A consumed dispatcher request is not completion evidence. Every physical increment still requires its own terminal M114/count/image/ledger audit and observation.
