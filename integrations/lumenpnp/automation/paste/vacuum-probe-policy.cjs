'use strict';

// Offline policy only. This module has no OpenPnP, transport, actuator, or clock access.
function fail(message) { throw new Error(message); }
function finite(value, name) {
  if (typeof value !== 'number' || !Number.isFinite(value)) fail(name + ' must be finite');
  return value;
}
function validate(c) {
  if (!c || !['increase', 'decrease'].includes(c.responseDirection)) fail('Explicit responseDirection contract required');
  ['startZmm', 'minZmm', 'stepMm', 'maxDescentMm', 'baselineTolerance', 'noiseFloor', 'candidateMinDelta', 'sampleIntervalMinMs', 'sampleIntervalMaxMs', 'maxDurationMs'].forEach(k => finite(c[k], k));
  if (!(c.startZmm > c.minZmm) || c.stepMm <= 0 || c.maxDescentMm <= 0 || c.startZmm - c.minZmm > c.maxDescentMm + 1e-9) fail('Invalid bounded descent');
  if (!Number.isInteger(c.baselineSamples) || c.baselineSamples < 3 || !Number.isInteger(c.samplesToConfirm) || c.samplesToConfirm < 2) fail('Sample counts must be explicit and bounded');
  if (c.baselineTolerance < 0 || c.noiseFloor < 0 || c.candidateMinDelta <= c.noiseFloor) fail('Invalid explicit sensor thresholds');
  if (c.sampleIntervalMinMs <= 0 || c.sampleIntervalMaxMs < c.sampleIntervalMinMs || c.maxDurationMs <= 0) fail('Invalid timing bounds');
  return c;
}
function createProbe(config, startedAtMs) {
  const c = validate(config);
  finite(startedAtMs, 'startedAtMs');
  return { config: { ...c }, phase: 'baseline', startedAtMs, lastAtMs: null, baseline: [], baselineValue: null,
    zmm: c.startZmm, targetZmm: null, levelSamples: [], descentMm: 0, samples: 0, result: null };
}
function outcome(state, decision, extra) { return Object.assign({ state, decision, zmm: state.zmm, descentMm: state.descentMm }, extra || {}); }
function stop(state, reason, decision) {
  state.phase = 'stopped';
  state.result = { kind: 'failed-closed', reason };
  return outcome(state, decision || 'abort', { reason });
}
function sample(state, value, atMs) {
  if (!state || !state.config) fail('Probe state required');
  if (state.phase === 'stopped' || state.phase === 'candidate') return outcome(state, state.phase === 'candidate' ? 'seal-candidate-no-contact-proof' : 'already-stopped', state.result);
  if (state.phase === 'awaiting-move') return stop(state, 'sample received before requested native Z move was acknowledged');
  const c = validate(state.config);
  if (!Number.isFinite(value)) return stop(state, 'sensor-failure: non-finite reading');
  if (!Number.isFinite(atMs)) return stop(state, 'sensor-failure: invalid timestamp');
  if (atMs < state.startedAtMs || atMs - state.startedAtMs > c.maxDurationMs) return stop(state, 'time-bound exceeded');
  if (state.lastAtMs !== null) {
    const dt = atMs - state.lastAtMs;
    if (dt < c.sampleIntervalMinMs || dt > c.sampleIntervalMaxMs) return stop(state, 'sample timing outside contract');
  }
  state.lastAtMs = atMs;
  state.samples++;
  if (state.samples > c.baselineSamples + (Math.ceil(c.maxDescentMm / c.stepMm) + 1) * c.samplesToConfirm) return stop(state, 'sample bound exceeded');

  if (state.phase === 'baseline') {
    state.baseline.push(value);
    if (state.baseline.length < c.baselineSamples) return outcome(state, 'collect-fresh-empty-baseline', { remaining: c.baselineSamples - state.baseline.length });
    const min = Math.min(...state.baseline), max = Math.max(...state.baseline);
    if (max - min > c.baselineTolerance) return stop(state, 'unstable empty baseline');
    state.baselineValue = state.baseline.reduce((a, b) => a + b, 0) / state.baseline.length;
    return requestMove(state, 'baseline-accepted-descend-one-increment');
  }

  const directedDelta = c.responseDirection === 'decrease' ? state.baselineValue - value : value - state.baselineValue;
  state.levelSamples.push(directedDelta);
  if (directedDelta > c.noiseFloor) {
    state.phase = 'confirming';
    const allCandidate = state.levelSamples.length >= c.samplesToConfirm && state.levelSamples.slice(-c.samplesToConfirm).every(d => d >= c.candidateMinDelta);
    if (allCandidate) {
      state.phase = 'candidate';
      state.result = { kind: 'seal-candidate', zmm: state.zmm, baseline: state.baselineValue, deltas: state.levelSamples.slice(-c.samplesToConfirm), contactVerified: false };
      return outcome(state, 'seal-candidate-stop-and-hold-z', state.result);
    }
    if (state.levelSamples.length >= c.samplesToConfirm) return stop(state, 'ambiguous or partial-seal deviation; hold Z and inspect');
    return outcome(state, 'hold-z-confirm-deviation', { sampleCount: state.levelSamples.length });
  }
  if (state.phase === 'confirming') return stop(state, 'deviation disappeared during confirmation; ambiguous partial seal');
  if (state.levelSamples.length < c.samplesToConfirm) return outcome(state, 'hold-z-confirm-no-deviation', { sampleCount: state.levelSamples.length });

  const proposed = nextZ(state);
  if (proposed === null) return stop(state, 'no seal within maximum bounded descent');
  return requestMove(state, 'descend-one-increment', proposed);
}
function requestMove(state, decision, proposed) {
  const next = proposed === undefined ? nextZ(state) : proposed;
  if (next === null) return stop(state, 'no seal within maximum bounded descent');
  state.targetZmm = next;
  state.phase = 'awaiting-move';
  return outcome(state, decision, { baseline: state.baselineValue, nextZmm: next });
}
function acknowledgeZMove(state, actualZmm, atMs) {
  if (!state || state.phase !== 'awaiting-move') return stop(state || { phase: 'stopped', result: null, zmm: NaN, descentMm: NaN }, 'unexpected Z-move acknowledgement');
  const c = validate(state.config);
  if (!Number.isFinite(actualZmm) || Math.abs(actualZmm - state.targetZmm) > 1e-6) return stop(state, 'native Z move did not reach exact requested target');
  if (!Number.isFinite(atMs) || atMs < state.lastAtMs || atMs - state.startedAtMs > c.maxDurationMs) return stop(state, 'time-bound exceeded during Z move');
  state.zmm = actualZmm;
  state.descentMm = c.startZmm - actualZmm;
  state.targetZmm = null;
  state.levelSamples = [];
  state.lastAtMs = atMs;
  state.phase = 'descent';
  return outcome(state, 'move-acknowledged-sample-at-current-z');
}
function nextZ(state) {
  const c = state.config;
  const next = Math.max(c.minZmm, Math.round((state.zmm - c.stepMm) * 1e9) / 1e9);
  if (next >= state.zmm - 1e-9 || c.startZmm - next > c.maxDescentMm + 1e-9) return null;
  return next;
}
function evaluateContactRepeatability(contactZsMm, toleranceMm, minimumCount) {
  finite(toleranceMm, 'toleranceMm');
  if (toleranceMm <= 0 || !Number.isInteger(minimumCount) || minimumCount < 2 || !Array.isArray(contactZsMm) || contactZsMm.length < minimumCount) return { consistent: false, reason: 'insufficient independently verified contacts or invalid tolerance' };
  if (contactZsMm.some(z => typeof z !== 'number' || !Number.isFinite(z))) return { consistent: false, reason: 'invalid contact Z' };
  const min = Math.min(...contactZsMm), max = Math.max(...contactZsMm);
  return { consistent: max - min <= toleranceMm, minZmm: min, maxZmm: max, spreadMm: max - min,
    meaning: 'Repeatability of externally verified contact observations only; sensor seal candidates are not contact observations.' };
}
module.exports = { createProbe, sample, acknowledgeZMove, evaluateContactRepeatability };
