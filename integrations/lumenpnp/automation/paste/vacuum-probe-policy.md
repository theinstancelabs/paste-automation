# Offline vacuum surface-probe policy

`vacuum-probe-policy.cjs` is a deterministic decision module. It has no machine, UI, serial, actuator, or clock access. Its inputs include a fresh sample stream and an explicit sensor response contract; unknown polarity or thresholds are rejected. The `increase`/`decrease` direction and all noise, candidate, repeatability, sample-count, timing, and descent limits must be justified and reviewed before a runtime supplies them. Historical N1 thresholds are not defaults.

The policy first collects a bounded, stable empty-nozzle baseline. It then permits one bounded Z decrement only after a complete quiet sample window. At the first reading outside the declared noise floor, it holds Z for confirmation; sustained response produces a **seal candidate**, while mixed or partial response, unstable baseline, timing/sensor error, and reaching the descent limit fail closed. No branch requests additional compression after a deviation. A seal candidate explicitly has `contactVerified: false`; it cannot establish a surface/contact calibration.

A deviation beyond the noise floor in the opposite direction to the declared response aborts immediately at the current Z. It is not a quiet sample and cannot permit further descent, including during candidate confirmation.

`evaluateContactRepeatability()` accepts only externally observed, independently verified contact Z observations. Callers must not pass seal-candidate Z values as confirmed contacts. Its tolerance and minimum count are explicit inputs, not assumed calibration. This module is policy scaffolding only; it is not connected to the native OpenPnP runtime and does not establish safe physical motion.

Run synthetic offline tests with `node --test automation/paste/vacuum-probe-policy.test.cjs` from `/home/lumen/lumenpnp`. Test values are illustrative and are not machine settings.
