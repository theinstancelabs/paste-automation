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
    rawBounds: Object.fromEntries(['X', 'Y', 'Z', 'A', 'B'].map(k => [k, { min: -100, max: k === 'Z' ? 58.2 : 100 }])),
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

// Extended work Z requires an explicitly rebuilt bounded profile.
{const p=profile();p.workZ=59.1;assert.throws(()=>P.validateProfile(p),/raw bounds/);p.rawBounds.Z.max=59.1;assert.equal(P.validateProfile(p).workZ,59.1);p.rawBounds.Z.max=60.01;assert.throws(()=>P.validateProfile(p),/maximum 60/);p.workZ=60.01;assert.throws(()=>P.validateProfile(p),/55..60/);}

// Vacuum onset provides relative slope only; an explicit needle zero is required.
{const p=profile();p.workZ=60;p.rawBounds.Z.max=60;p.vacuumReference={plane:{a:.01,b:0,c:4.5}};Object.values(p.pads).forEach(pads=>Object.values(pads).forEach(t=>t.gapAtWorkZ=null));P.validateProfile(p);
 const r={...recipe,workZ:60,heightMode:'gap',gapMm:.2};assert.throws(()=>P.plan(['R1'],r,p,start,0,0),/needle touch/);
 const touched=P.applyNeedleTouch(p,p.vacuumReference,{ref:'R1',pad:'1',rawZ:59.5});
 assert.equal(touched.pads.R1['1'].touchRawZ,59.5);assert(Math.abs(touched.pads.R2['1'].touchRawZ-59.4)<1e-9);
 const plan=P.plan(['R1','R2'],r,touched,start,0,0);const doses=plan.stages.filter(s=>s.tag==='dose');assert.equal(doses.length,4);
 const beforeDoses=[];let z=start.Z;for(const st of plan.stages){if(st.axis==='Z')z=st.target;if(st.tag==='dose')beforeDoses.push(z);}assert.deepEqual(beforeDoses,[59.3,59.28,59.2,59.18]);
 assert.throws(()=>P.plan(['R1'],{...r,gapMm:.1},touched,start,0,0),/0.15/);
 assert.throws(()=>P.plan(['R1'],{...r,heightMode:'raw',workZ:59.5},touched,start,0,0),/gap/);
}
{const p=profile();p.heightCalibrationPending=true;Object.values(p.pads).forEach(ps=>Object.values(ps).forEach(t=>t.gapAtWorkZ=null));P.validateProfile(p);assert.throws(()=>P.plan(['R1'],recipe,p,start,0,0),/New height calibration/);}

{const p=profile(),v={plane:{a:.01,b:0,c:4.5}},m={cameraXY:[15,20],rawZ:57.75,operatorConfirmedBarelyTouching:true};const result=P.applyNeedleTouch(p,v,m);assert.equal(result.pads.R1['1'].touchRawZ,57.8);assert.equal(result.pads.R2['1'].touchRawZ,57.7);assert.throws(()=>P.applyNeedleTouch(p,v,{...m,operatorConfirmedBarelyTouching:false}),/explicit operator/);assert.throws(()=>P.applyNeedleTouch(p,v,{...m,cameraXY:[NaN,20]}),/finite/);}
{const current={raw:{X:1,Y:2,Z:57.75,A:200,B:-10},driver:{X:1,Y:2,Z:57.75,A:200,B:-10}};P.validateManualHandoff(current,-10);assert.throws(()=>P.validateManualHandoff(current,-11),/B changed/);assert.throws(()=>P.validateManualHandoff({...current,driver:{...current.driver,Z:57.7}},-10),/raw\/driver/);}

{const raw={X:359.19686795875464,Y:183.97952903288106,Z:32.25,A:200,B:-4647.48},driver={...raw,X:359.2,Y:183.98};P.validateManualHandoff({raw,driver},raw.B);assert.throws(()=>P.validateManualHandoff({raw,driver:{...driver,X:359.21}},raw.B),/mismatch/);assert.throws(()=>P.validateManualHandoff({raw,driver:{...driver,B:raw.B+.001}},raw.B),/mismatch/);}
