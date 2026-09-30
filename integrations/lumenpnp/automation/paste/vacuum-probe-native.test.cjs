'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const n = require('./vacuum-probe-native.cjs');
const policy = require('./vacuum-probe-policy.cjs');

function request() {
  const q = JSON.parse(fs.readFileSync(__dirname + '/vacuum-probe-native.pending.json'));
  Object.assign(q, {
    id: '12345678-1234-1234-1234-123456789abc', createdMs: 100000, jvmStartMs: 42,
    operator: 'synthetic only', liveConfigurationSha256: 'a'.repeat(64), expectedLeftTipId: 'test-tip',
    targetSurfaceIdentity: 'synthetic restrained flat coupon area', reviewRecord: 'review-123',
    operatorVerifiedEmptyFreeAirBaseline: true, operatorVerifiedProbeTarget: true,
    operatorVerifiedJointEnvelope: true, bothHeadsClearAlongEnvelope: true,
    motionAreaClear: true, noHeldPartsObserved: true, n2Quarantined: true,
    expectedRaw: { X: 1, Y: 2, Z: 26.5, A: 3, B: 720 },
    expectedDriver: { X: 1, Y: 2, Z: 26.5, A: 3, B: 720 },
    stationaryEvidence: { path: '/synthetic/start.png', sha256: 'b'.repeat(64), capturedMs: 99000 },
    targetEvidence: { path: '/synthetic/target.png', sha256: 'c'.repeat(64), capturedMs: 99000 },
    jointEnvelopeEvidence: { path: '/synthetic/envelope.png', sha256: 'd'.repeat(64), capturedMs: 99000 },
    baselineContractEvidence: { path: '/synthetic/baseline.json', sha256: 'e'.repeat(64), reviewedMs: 99000 },
    barrierEvidence: { path: '/synthetic/barrier.json', sha256: 'f'.repeat(64) },
    jointInterval: { minRawZ: 24.5, maxRawZ: 26.5, reviewedForCurrentPose: true, reviewRecord: 'review-123' },
    nativeZConfiguration: { softLowEnabled: false, softLowMm: 0, softHighEnabled: false, softHighMm: 0,
      safeLowEnabled: true, safeLowMm: 26.5, safeHighEnabled: true, safeHighMm: 36.5 },
    contract: { responseDirection: 'decrease', startZmm: 26.5, floorZmm: 24.5, maxDescentMm: 2,
      stepMm: 0.05, baselineSamples: 8, baselineTolerance: 1, noiseFloor: 1, candidateMinDelta: 4,
      samplesToConfirm: 2, baselineIntervalMinMs: 100, baselineIntervalMaxMs: 1000,
      sampleIntervalMinMs: 100, sampleIntervalMaxMs: 1000, maxDurationMs: 180000,
      offBaselineSamples: 3, offBaselineTolerance: 1, expectedEmptyMean: 232.25, expectedEmptyTolerance: 1.5, minimumPumpResponseDelta: 10 }
  });
  q.expectedNativePoses = {};
  for (const k of ['N1', 'N2', 'top', 'bottom']) q.expectedNativePoses[k] = { x: 1, y: 2, z: 3, rotation: 4 };
  return q;
}

test('requires fresh identity, exact target/evidence and jointly bounded Z contract', () => {
  const q = request();
  assert.equal(n.validate(q, 100001, 42), q);
  for (const edit of [
    x => { x.targetSurfaceIdentity = ''; }, x => { x.operatorVerifiedProbeTarget = false; },
    x => { x.n2Quarantined = false; }, x => { x.contract.responseDirection = null; },
    x => { x.contract.maxDescentMm = 2.05; }, x => { x.contract.stepMm = 0.1; },
    x => { x.contract.floorZmm = 24.51; }, x => { x.contract.candidateMinDelta = 1; },
    x => { x.targetEvidence.sha256 = 'bad'; }, x => { x.jointInterval.minRawZ = 24.4; }
  ]) { const bad = request(); edit(bad); assert.throws(() => n.validate(bad, 100001, 42)); }
  assert.throws(() => n.validate(q, 100001, 43), /JVM/);
  assert.throws(() => n.validate(q, 400001, 42), /Stale/);
});

test('enforces exact 0.05 mm target arithmetic and hard 2 mm bound', () => {
  assert.equal(n.target(26.5, 0.05, 0), 26.45);
  assert.equal(n.target(26.5, 0.05, 39), 24.5);
  assert.throws(() => n.target(26.5, 0.1, 0), /0.05/);
  assert.throws(() => n.target(26.5, 0.05, 40), /2 mm/);
});

test('rejects malformed, duplicate, absent, and faulted sensor responses', () => {
  assert.equal(n.parseByte('233'), 233);
  assert.equal(n.parseSensorResponse(['ok', 'data:233'], true), 233);
  for (const lines of [[], ['data:256'], ['data:-1'], ['data:1', 'data:2'], ['Error: reset', 'data:233'], ['Resend: 2']])
    assert.throws(() => n.parseSensorResponse(lines, true));
});

test('requires exactly two observed controller microsteps per 0.05 mm raw-Z step', () => {
  const lines = ['X:1.00 Y:2.00 Z:26.45 A:3.00 B:720.00 Count X:40 Y:80 Z:1058 A:12 B:28800', 'ok'];
  const c = n.parseStepCount(lines);
  assert.equal(c.Z, 1058);
  n.compareOneStepCounts({ X: 40, Y: 80, Z: 1060, A: 12, B: 28800 }, c, 'Z', -2, 'step');
  assert.throws(() => n.compareOneStepCounts({ X: 40, Y: 80, Z: 1060, A: 12, B: 28800 }, { ...c, Z: 1059 }, 'Z', -2, 'step'), /microstep/);
  assert.throws(() => n.parseStepCount(['X:1 Y:2 Z:3 A:4 B:5']));
});

test('vacuum deviation holds at current Z and policy never proposes a compression step', () => {
  const c = { responseDirection: 'decrease', startZmm: 26.5, minZmm: 24.5, stepMm: 0.05,
    maxDescentMm: 2, baselineSamples: 8, baselineTolerance: 1, noiseFloor: 1,
    candidateMinDelta: 4, samplesToConfirm: 2, sampleIntervalMinMs: 100,
    sampleIntervalMaxMs: 1000, maxDurationMs: 180000 };
  const p = policy.createProbe(c, 0); let r;
  for (let i = 0; i < 8; i++) r = policy.sample(p, 232, i * 100);
  assert.equal(r.nextZmm, 26.45);
  policy.acknowledgeZMove(p, 26.45, 800);
  r = policy.sample(p, 230, 900);
  assert.equal(r.decision, 'hold-z-confirm-deviation');
  assert.equal(r.zmm, 26.45);
  r = policy.sample(p, 227, 1000);
  assert.equal(r.decision, 'abort', 'mixed onset is ambiguous and stops');
  assert.equal(p.zmm, 26.45);
  assert.equal(p.targetZmm, null);
});

test('barrier must be same JVM/config, fresh, read-only and exact at target', () => {
  const q = request();
  const record = { status: 'completed-read-only-position-barrier', noMotionCommandSubmitted: true,
    controllerPositionVerified: true, uncertainCompletion: false, finishedAt: new Date(99990).toISOString(),
    liveConfigurationSha256: q.liveConfigurationSha256, request: { jvmStartMs: 42, liveConfigurationSha256: q.liveConfigurationSha256 },
    reported: q.expectedRaw, afterQuerySnapshot: { raw: q.expectedRaw, driver: q.expectedDriver, nativePoses: q.expectedNativePoses } };
  assert.equal(n.barrier(record, q, 100000, 42), record);
  assert.throws(() => n.barrier({ ...record, noMotionCommandSubmitted: false }, q, 100000, 42), /no-motion/);
  assert.throws(() => n.barrier({ ...record, finishedAt: new Date(1).toISOString() }, q, 400001, 42), /stale/);
});

test('historical baseline requires the exact reviewed report, identity, and no-motion status', () => {
  const crypto = require('node:crypto');
  const report = { status: 'completed-free-air-baseline-awaiting-review', motionSubmitted: false, controllerPositionVerified: true, normalOffAcknowledged: true, uncertainCompletion: false, physicalAcceptanceEstablished: false, request: {id: 'synthetic', scope: 'stationary-N1-VAC1-free-air-baseline', createdMs: 80000, jvmStartMs: 42, liveConfigurationSha256: '1'.repeat(64), expectedLeftTipId: 'test-tip'}, baseline: {finalOffAcknowledged: true, offSummary: {count: 8, mean: 255, spread: 0}, onSummary: {count: 8, mean: 232.25, spread: 1, acceptanceEstablished: false}} };
  const bytes = Buffer.from(JSON.stringify(report));
  const digest = crypto.createHash('sha256').update(bytes).digest('hex');
  const q = request(); q.createdMs = report.request.createdMs + 10000;
  q.jvmStartMs = report.request.jvmStartMs;
  q.liveConfigurationSha256 = report.request.liveConfigurationSha256;
  q.expectedLeftTipId = report.request.expectedLeftTipId;
  q.baselineContractEvidence.sha256 = digest;
  assert.equal(n.validateBaselineReference(report, q, digest).emptyOnMean, 232.25);
  assert.throws(() => n.validateBaselineReference(report, q, '0'.repeat(64)), /hash/);
  assert.throws(() => n.validateBaselineReference({ ...report, status: 'failed' }, q, digest), /report/);
  assert.throws(() => n.validateBaselineReference({ ...report, request: { ...report.request, jvmStartMs: 1 } }, q, digest), /JVM/);
  assert.throws(() => n.validateBaselineReference({ ...report, request: { ...report.request, liveConfigurationSha256: 'bad' } }, q, digest), /config/);
  assert.throws(() => n.validateBaselineReference({ ...report, request: { ...report.request, expectedLeftTipId: 'wrong' } }, q, digest), /tip/);
});
