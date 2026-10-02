'use strict';
const assert = require('node:assert/strict');
const P = require('../operator-console-policy.cjs');

function profile() {
  const pads = {};
  for (const [i, ref] of ['R1', 'R2'].entries()) {
    const x = 10 + i * 10;
    pads[ref] = {
      '1': { cameraXY: [x, 20], tipXY: [x - 1, 20], gapAtWorkZ: 0.5 },
      '2': { cameraXY: [x + 2, 20], tipXY: [x + 1, 20], gapAtWorkZ: 0.5 },
    };
  }
  return {
    schema: 1, id: 'a'.repeat(64), sessionId: '12345678-1234-1234-1234-123456789abc', name: 'test',
    jvmStartMs: 1, liveConfigurationSha256: 'b'.repeat(64), safeZ: 32.25, travelZ: 53.45, workZ: 58.2,
    gapUncertaintyMm: 0.3, pads,
    expectedRaw: { X: 0, Y: 0, Z: 32.25, A: 200, B: -10 },
    expectedDriver: { X: 0, Y: 0, Z: 32.25, A: 200, B: -10 },
    expectedNativePoses: Object.fromEntries(['N1', 'N2', 'top', 'bottom'].map(k => [k, { x: 0, y: 0, z: 32.25, rotation: 0 }])),
    rawBounds: Object.fromEntries(['X', 'Y', 'Z', 'A', 'B'].map(k => [k, { min: -100, max: 100 }])),
    headClearanceBounds: Object.fromEntries(['N1', 'N2'].map(k => [k, { minX: -100, maxX: 100, minY: -100, maxY: 100, minZ: 0, maxZ: 100 }])),
    sourceEvidence: [{ path: '/test', sha256: 'c'.repeat(64) }],
    rodBudget: { baselineGrossDegrees: 1, baselineB: -10, maximumAdditionalGrossDegrees: 100 },
  };
}

const p = P.validateProfile(profile());
const recipe = { padMode: 'both', doseDegrees: 6, retractPercent: 15, dwellMs: 2000, retractDwellMs: 500, bSpeedFraction: 0.05, workZ: 58.2 };
P.validateRecipe(recipe, p);
assert.throws(() => P.validateRecipe({ ...recipe, doseDegrees: NaN }, p), /finite/);
assert.throws(() => P.validateRecipe({ ...recipe, workZ: 58.21 }, p), /grid/);

const start = { X: 0, Y: 0, Z: 32.25, A: 200, B: -10 };
const first = P.plan(['R1'], recipe, p, start, 0, 0);
assert.equal(first.pendingRetractDegrees, 0.9);
assert(Math.abs(first.grossDegrees - 12.9) < 1e-9);
const retractIndex = first.stages.findIndex(s => s.tag === 'inter-resistor-retract');
assert(retractIndex > first.stages.findIndex(s => s.tag === 'dose'));
assert.equal(first.finalRaw.Z, p.safeZ);

// A separate click must preserve the relief and restore it only after reaching
// the next pad's work position, immediately before the next dose.
const next = P.plan(['R2'], recipe, p, first.finalRaw, first.grossDegrees, first.pendingRetractDegrees);
const restore = next.stages.findIndex(s => s.tag === 'restore-prior-inter-resistor-retract');
const dose = next.stages.findIndex(s => s.tag === 'dose');
assert(restore >= 0 && dose > restore);
assert(next.stages.slice(0, restore).some(s => s.axis === 'X' || s.axis === 'Y'));
assert(next.stages.slice(0, restore).some(s => s.axis === 'Z' && s.target === recipe.workZ));
assert.equal(next.pendingRetractDegrees, first.pendingRetractDegrees);
assert.throws(() => P.plan(['R1'], recipe, p, start, 99, 0), /budget exhausted/);
let previous={...start};for(const step of first.stages){if(['X','Y'].includes(step.axis))assert(Math.abs(step.target-previous[step.axis])<=10.000001);if(step.axis==='Z')assert(Math.abs(step.target-previous.Z)<=5.000001);previous[step.axis]=step.target;}assert.equal(previous.X,p.pads.R1['2'].tipXY[0]);assert.equal(previous.Y,p.pads.R1['2'].tipXY[1]);
console.log('operator policy checks passed');
