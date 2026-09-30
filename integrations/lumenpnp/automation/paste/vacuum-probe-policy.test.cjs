'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createProbe, sample, acknowledgeZMove, evaluateContactRepeatability } = require('./vacuum-probe-policy.cjs');

// Synthetic-only contract and sensor traces; values are not machine calibration.
function contract(overrides = {}) {
  return { responseDirection: 'decrease', startZmm: 8, minZmm: 7, stepMm: 0.2, maxDescentMm: 1,
    baselineSamples: 4, baselineTolerance: 0.5, noiseFloor: 1, candidateMinDelta: 3,
    samplesToConfirm: 2, sampleIntervalMinMs: 10, sampleIntervalMaxMs: 200, maxDurationMs: 5000, ...overrides };
}
function baseline(p, start = 0, values = [100, 100.2, 99.9, 100.1]) {
  let r;
  values.forEach((v, i) => { r = sample(p, v, start + i * 20); });
  if (r.decision === 'baseline-accepted-descend-one-increment') return acknowledgeZMove(p, r.nextZmm, start + values.length * 20);
  return r;
}
function level(p, values, t) { let r; values.forEach((v, i) => { r = sample(p, v, t + i * 20); }); return r; }

test('requires explicit response direction and bounded sensor contract', () => {
  assert.throws(() => createProbe({ ...contract(), responseDirection: undefined }, 0), /responseDirection/);
  assert.throws(() => createProbe(contract({ maxDescentMm: 0.05 }), 0), /bounded descent/);
});
test('requires fresh stable empty baseline before offering first incremental Z', () => {
  const p = createProbe(contract(), 0);
  const first = sample(p, 100, 20);
  assert.equal(first.decision, 'collect-fresh-empty-baseline');
  assert.equal(p.phase, 'baseline');
  const done = level(p, [100.2, 99.9, 100.1], 40);
  assert.equal(done.decision, 'baseline-accepted-descend-one-increment');
  assert.equal(done.nextZmm, 7.8);
  assert.equal(p.zmm, 8, 'requested move must not be reported as actual position');
  assert.equal(acknowledgeZMove(p, 7.8, 110).zmm, 7.8);
});
test('unstable baseline fails closed without descent', () => {
  const p = createProbe(contract(), 0);
  const r = baseline(p, 0, [100, 100.1, 100.2, 102]);
  assert.match(r.reason, /unstable/);
  assert.equal(p.zmm, 8);
});
test('all native descent steps require a quiet sample window and stay inside max descent', () => {
  const p = createProbe(contract({ stepMm: 0.3, minZmm: 7.1, maxDescentMm: 0.9 }), 0);
  baseline(p);
  let t = 100;
  let end;
  for (const expected of [7.4, 7.1]) {
    end = level(p, [100, 100], t); t += 100;
    assert.equal(end.decision, 'descend-one-increment');
    end = acknowledgeZMove(p, expected, t); t += 20;
    assert.ok(Math.abs(p.zmm - expected) < 1e-9);
  }
  end = level(p, [100, 100], t);
  assert.equal(end.decision, 'abort');
  assert.match(end.reason, /maximum bounded descent/);
  assert.equal(p.zmm, 7.1);
});
test('sustained explicitly directed response returns seal candidate at same Z, never contact proof', () => {
  const p = createProbe(contract(), 0);
  baseline(p);
  const held = level(p, [95, 95], 100);
  assert.equal(held.decision, 'seal-candidate-stop-and-hold-z');
  assert.equal(held.zmm, 7.8);
  assert.equal(held.contactVerified, false);
  assert.equal(sample(p, 90, 300).decision, 'seal-candidate-no-contact-proof');
});
test('ambiguous partial seal halts at first deviating level without another descent', () => {
  const p = createProbe(contract(), 0);
  baseline(p);
  assert.equal(sample(p, 98.5, 100).decision, 'hold-z-confirm-deviation');
  const r = sample(p, 98.6, 120);
  assert.equal(r.decision, 'abort');
  assert.match(r.reason, /ambiguous or partial-seal/);
  assert.equal(p.zmm, 7.8);
});
test('opposite-sign deviation aborts at the same Z for either polarity and cannot resume descent', () => {
  for (const responseDirection of ['decrease', 'increase']) {
    for (const alreadyConfirming of [false, true]) {
      const p = createProbe(contract({ responseDirection }), 0);
      baseline(p, 0, [100, 100, 100, 100]);
      if (alreadyConfirming) {
        const expectedSign = responseDirection === 'decrease' ? 98 : 102;
        assert.equal(sample(p, expectedSign, 100).decision, 'hold-z-confirm-deviation');
      }
      const wrongSign = responseDirection === 'decrease' ? 102 : 98;
      const r = sample(p, wrongSign, alreadyConfirming ? 120 : 100);
      assert.equal(r.decision, 'abort');
      assert.match(r.reason, /opposite-sign/);
      assert.equal(p.zmm, 7.8);
      assert.equal(p.targetZmm, null);
      assert.equal(sample(p, 100, 140).decision, 'already-stopped');
    }
  }
});
test('sensor failure, too-fast/late samples, and elapsed deadline fail closed', () => {
  const failed = createProbe(contract(), 0);
  assert.match(sample(failed, NaN, 20).reason, /sensor-failure/);
  const fast = createProbe(contract(), 0);
  sample(fast, 100, 20);
  assert.match(sample(fast, 100, 21).reason, /timing/);
  const late = createProbe(contract({ maxDurationMs: 80 }), 0);
  assert.match(sample(late, 100, 81).reason, /time-bound/);
});
test('repeated contact consistency accepts only enough finite independently supplied observations', () => {
  assert.equal(evaluateContactRepeatability([5, 5.04, 4.98], 0.1, 3).consistent, true);
  assert.equal(evaluateContactRepeatability([5, 5.4, 5.1], 0.1, 3).consistent, false);
  assert.equal(evaluateContactRepeatability([5], 0.1, 3).consistent, false);
  assert.equal(evaluateContactRepeatability([5, NaN, 5], 0.1, 3).consistent, false);
});
