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
