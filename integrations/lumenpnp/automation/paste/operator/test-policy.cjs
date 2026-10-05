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
{const p=profile();p.workZ=59.1;assert.throws(()=>P.validateProfile(p),/raw bounds/);p.rawBounds.Z.max=59.1;assert.equal(P.validateProfile(p).workZ,59.1);p.rawBounds.Z.max=63.01;assert.throws(()=>P.validateProfile(p),/maximum 63/);p.workZ=63.01;assert.throws(()=>P.validateProfile(p),/55..63/);}

// Vacuum onset provides relative slope only; an explicit needle zero is required.
{const p=profile();p.workZ=60;p.rawBounds.Z.max=60;p.vacuumReference={plane:{a:.01,b:0,c:4.5}};Object.values(p.pads).forEach(pads=>Object.values(pads).forEach(t=>t.gapAtWorkZ=null));P.validateProfile(p);
 const r={...recipe,workZ:60,heightMode:'gap',gapMm:.2};assert.throws(()=>P.plan(['R1'],r,p,start,0,0),/needle touch/);
 const touched=P.applyNeedleTouch(p,p.vacuumReference,{ref:'R1',pad:'1',rawZ:59.5});
 assert.equal(touched.pads.R1['1'].touchRawZ,59.5);assert(Math.abs(touched.pads.R2['1'].touchRawZ-59.4)<1e-9);
 const plan=P.plan(['R1','R2'],r,touched,start,0,0);const doses=plan.stages.filter(s=>s.tag==='dose');assert.equal(doses.length,4);
 const beforeDoses=[];let z=start.Z;for(const st of plan.stages){if(st.axis==='Z')z=st.target;if(st.tag==='dose')beforeDoses.push(z);}assert.deepEqual(beforeDoses,[59.3,59.28,59.2,59.18]);
 assert.throws(()=>P.plan(['R1'],{...r,gapMm:.09},touched,start,0,0),/0.10/);
 assert.throws(()=>P.plan(['R1'],{...r,heightMode:'raw',workZ:59.5},touched,start,0,0),/gap/);
}
{const p=profile();p.heightCalibrationPending=true;Object.values(p.pads).forEach(ps=>Object.values(ps).forEach(t=>t.gapAtWorkZ=null));P.validateProfile(p);assert.throws(()=>P.plan(['R1'],recipe,p,start,0,0),/New height calibration/);}

{const p=profile(),v={plane:{a:.01,b:0,c:4.5}},m={cameraXY:[15,20],rawZ:57.75,operatorConfirmedBarelyTouching:true};const result=P.applyNeedleTouch(p,v,m);assert.equal(result.pads.R1['1'].touchRawZ,57.8);assert.equal(result.pads.R2['1'].touchRawZ,57.7);assert.throws(()=>P.applyNeedleTouch(p,v,{...m,operatorConfirmedBarelyTouching:false}),/explicit operator/);assert.throws(()=>P.applyNeedleTouch(p,v,{...m,cameraXY:[NaN,20]}),/finite/);}
{const current={raw:{X:1,Y:2,Z:57.75,A:200,B:-10},driver:{X:1,Y:2,Z:57.75,A:200,B:-10}};P.validateManualHandoff(current,-10);assert.throws(()=>P.validateManualHandoff(current,-11),/B changed/);assert.throws(()=>P.validateManualHandoff({...current,driver:{...current.driver,Z:57.7}},-10),/raw\/driver/);}

{const raw={X:359.19686795875464,Y:183.97952903288106,Z:32.25,A:200,B:-4647.48},driver={...raw,X:359.2,Y:183.98};P.validateManualHandoff({raw,driver},raw.B);assert.throws(()=>P.validateManualHandoff({raw,driver:{...driver,X:359.21}},raw.B),/mismatch/);assert.throws(()=>P.validateManualHandoff({raw,driver:{...driver,B:raw.B+.01}},raw.B),/mismatch/);}

{const p=profile();p.rodBudget.maximumAdditionalGrossDegrees=12000;P.validateProfile(p);const evidence={planningRemainingMm:19.6737783,mmPerMotorDegreeNominal:.0008246527777777778};const capacity=P.validateRodCapacity(p.rodBudget,evidence);assert(Math.abs(capacity.plannedTravelMm-9.895833333333334)<1e-9);assert.throws(()=>P.validateRodCapacity(p.rodBudget,{...evidence,planningRemainingMm:9}),/capacity/);p.rodBudget.maximumAdditionalGrossDegrees=24201;assert.throws(()=>P.validateProfile(p),/planning budget/);assert.throws(()=>P.validateRodCapacity(p.rodBudget,evidence),/capacity/);}

{const raw={X:10,Y:20,Z:32.25,A:200,B:87.97308191775504},driver={...raw,B:87.97};P.validateManualHandoff({raw,driver},87.97);assert.throws(()=>P.validateManualHandoff({raw,driver},88.97),/B changed/);assert.throws(()=>P.validateManualHandoff({raw,driver:{...driver,B:88.97}},87.97),/mismatch/);}

{const p=profile();p.workZ=61.4;assert.throws(()=>P.validateProfile(p),/raw bounds/);p.rawBounds.Z.max=61.4;P.validateProfile(p);}

{const p=profile();p.workZ=60;p.rawBounds.Z.max=63;p.calibrationRawZMax=63;P.validateProfile(p);p.calibrationRawZMax=63.1;assert.throws(()=>P.validateProfile(p),/Calibration Z/);p.calibrationRawZMax=63;p.rawBounds.Z.max=62;assert.throws(()=>P.validateProfile(p),/Calibration Z/);}
assert.throws(()=>P.plan(['R1'],recipe,p,start,0,15.01),/Large relief: purge/);
assert.throws(()=>P.plan(['R1'],recipe,p,start,0,27),/Large relief: purge/);
assert(P.plan(['R1'],recipe,p,start,0,0).stages.length>0);

const verifiedB=(from,to,tag,verified=true)=>({axis:'B',startRaw:{B:from},reportedRaw:{B:to},tag,verified});
assert.equal(P.pendingFromVerifiedStages(1.2,[]),1.2);
assert.equal(P.pendingFromVerifiedStages(1.2,[verifiedB(10,8.8,'restore-prior-inter-resistor-retract'),verifiedB(8.8,2.8,'dose'),verifiedB(2.8,3.7,'inter-resistor-retract')]),.9);
assert.equal(P.pendingFromVerifiedStages(1.2,[verifiedB(10,8.8,'restore-prior-inter-resistor-retract'),verifiedB(8.8,2.8,'dose',false)]),0);
{const independent=P.plan(['R1'],{...recipe,bSpeedFraction:.04,retractSpeedFraction:.2},p,start,0,1);assert.equal(independent.stages.find(s=>s.tag==='dose').speedFraction,.04);assert.equal(independent.stages.find(s=>s.tag==='restore-prior-inter-resistor-retract').speedFraction,.04);assert.equal(independent.stages.find(s=>s.tag==='inter-resistor-retract').speedFraction,.2);assert.throws(()=>P.validateRecipe({...recipe,retractSpeedFraction:2},p),/Retract speed/);}
{const ref={rawZ:58.4,operatorConfirmedCoplanar:true,evidence:{path:'/synthetic/report.json',sha256:'a'.repeat(64)}},flat=P.applyCoplanarTouch({...p,calibrationRawZMax:63},ref);assert.equal(flat.pads.R1['1'].touchRawZ,58.4);assert.equal(flat.pads.R2['2'].touchRawZ,58.4);assert(!flat.vacuumReference);assert.throws(()=>P.applyCoplanarTouch(p,{...ref,operatorConfirmedCoplanar:false}),/confirmation/);assert.throws(()=>P.applyCoplanarTouch(p,{...ref,evidence:{}}),/evidence/);}

{const q=profile();q.rawBounds.Z.max=60;q.workZ=60;q.calibrationRawZMax=63;const flat=P.applyCoplanarTouch(q,{rawZ:58.4,operatorConfirmedCoplanar:true,evidence:{path:'/synthetic/touch',sha256:'a'.repeat(64)}});const r={...recipe,workZ:60,heightMode:'gap',gapMm:.10},plan=P.plan(['R1'],r,flat,start,0,0);assert(plan.stages.some(s=>s.axis==='Z'&&s.target===58.3));assert.throws(()=>P.plan(['R1'],{...r,gapMm:.099},flat,start,0,0),/0.10/);}
{const q=profile();q.workZ=59.15;q.rawBounds.Z.max=63;q.calibrationRawZMax=63;const datum={surfaceIdentity:'demo PCB',assumption:'single-point-flat-plane-approximation',rawZ:59.35,operatorConfirmedBoardTouch:true,evidence:{path:'/synthetic/demo-touch.json',sha256:'a'.repeat(64)}},flat=P.applyBoardTouch(q,datum),pending=P.withCalibration(q,{alignmentApplied:false,boardTouchReference:datum});assert.equal(flat.heightDatum,'single-point-demo-board-touch-flat-plane-approximation-tilt-unmeasured');assert.equal(flat.pads.R1['1'].touchRawZ,59.35);assert(Math.abs(flat.pads.R2['2'].gapAtWorkZ-.2)<1e-9);assert.deepEqual(pending.pads.R1['1'].cameraXY,q.pads.R1['1'].cameraXY);assert.equal(pending.pads.R1['1'].touchRawZ,59.35);assert.throws(()=>P.applyBoardTouch(q,{...datum,surfaceIdentity:'rear scrap'}));assert.throws(()=>P.applyBoardTouch(q,{...datum,operatorConfirmedBoardTouch:false}));assert.throws(()=>P.applyBoardTouch(q,{...datum,assumption:'measured-plane'}));}

{const q=profile();q.pads.R3=JSON.parse(JSON.stringify(q.pads.R1));q.pads.R3['1'].cameraXY=[20,60];q.pads.R3['1'].tipXY=[19,60];q.pads.R3['2'].cameraXY=[22,60];q.pads.R3['2'].tipXY=[21,60];Object.values(q.pads).forEach(ps=>Object.values(ps).forEach(t=>{t.touchRawZ=57.5;}));const samples=['R1','R2','R3'].map(ref=>({ref,cameraXY:P.center(q,ref)}));const corr={profileId:q.id,sessionId:q.sessionId,basis:'repeated-deposit-centroid-offset',deltaRawXY:[.4,-.25],evidence:{path:'/synthetic/centroids.json',sha256:'f'.repeat(64)}},datum={rawZ:57.9,surfaceIdentity:'demo PCB',assumption:'single-point-flat-plane-approximation',operatorConfirmedBoardTouch:true,evidence:{path:'/synthetic/touch.json',sha256:'e'.repeat(64)}},sidecar={alignmentApplied:true,zApplied:true,alignmentSamples:samples,boardTouchReference:datum,tipXYCorrection:corr},plain=P.withCalibration(q,{...sidecar,tipXYCorrection:undefined}),fixed=P.withCalibration(q,sidecar);for(const ref of Object.keys(q.pads))for(const pad of ['1','2']){assert.deepEqual(fixed.pads[ref][pad].cameraXY,plain.pads[ref][pad].cameraXY);assert.deepEqual(fixed.pads[ref][pad].tipXY,[Math.round((plain.pads[ref][pad].tipXY[0]+.4)*100)/100,Math.round((plain.pads[ref][pad].tipXY[1]-.25)*100)/100]);assert.equal(fixed.pads[ref][pad].touchRawZ,plain.pads[ref][pad].touchRawZ);}assert.throws(()=>P.withCalibration(q,{...sidecar,zApplied:false}),/applied XY and height/);}

{const q=profile();q.rodBudget.maximumAdditionalGrossDegrees=23800;P.validateProfile(q);const e={planningRemainingMm:19.6737783,mmPerMotorDegreeNominal:.0008246527777777778};assert(P.validateRodCapacity(q.rodBudget,e).plannedTravelMm<e.planningRemainingMm);assert.throws(()=>P.validateRodCapacity(q.rodBudget,{...e,planningRemainingMm:19}),/capacity/);}

{const q=profile();q.rodBudget.maximumAdditionalGrossDegrees=1000;q.rawBounds.B={min:-1010,max:990};for(const dose of [60,120]){const r={...recipe,doseDegrees:dose,retractPercent:0},plan=P.plan(['R1'],r,q,start,0,0);assert.equal(plan.grossDegrees,dose*2);assert.equal(plan.stages.filter(s=>s.tag==='dose').length,2);assert.equal(plan.endB,start.B-dose*2);}assert.throws(()=>P.validateRecipe({...recipe,doseDegrees:121},q),/0.25..120/);}
{const q=profile();q.pads.D33=JSON.parse(JSON.stringify(q.pads.R1));P.validateProfile(q);assert(P.plan(['D33'],recipe,q,start,0,0).stages.length);assert.throws(()=>P.plan(['D34'],recipe,q,start,0,0),/missing/);q.pads.D41=q.pads.D33;assert.throws(()=>P.validateProfile(q),/registered/);}

{const q=profile();q.rodBudget.maximumAdditionalGrossDegrees=1000;q.rawBounds.B={min:-1010,max:990};const r={...recipe,doseDegrees:100,retractPercent:10,retractEachPad:true,retractSpeedFraction:1},plan=P.plan(['R1','R2'],r,q,start,0,0);assert.equal(plan.grossDegrees,470);assert.equal(plan.pendingRetractDegrees,10);assert.equal(plan.stages.filter(s=>s.tag==='inter-resistor-retract').length,4);assert.equal(plan.stages.filter(s=>s.tag==='restore-prior-inter-resistor-retract').length,3);for(let i=0;i<plan.stages.length;i++)if(plan.stages[i].tag==='dose'){assert.equal(plan.stages[i+1].tag,'inter-resistor-retract');assert.equal(plan.stages[i+1].speedFraction,1);}assert.throws(()=>P.validateRecipe({...r,retractEachPad:'true'},q),/boolean/);const old=P.plan(['R1','R2'],{...r,retractEachPad:false},q,start,0,0);assert.equal(old.grossDegrees,430);}
{const q=profile();q.rodBudget.maximumAdditionalGrossDegrees=1000;q.rawBounds.B={min:-1010,max:990};for(const doseDegrees of [60,90]){const r={...recipe,doseDegrees,retractPercent:50,retractDegrees:6,retractEachPad:true},plan=P.plan(['R1','R2'],r,q,start,0,0);assert.deepEqual(plan.stages.filter(s=>s.tag==='inter-resistor-retract').map((s,i,a)=>{const before=plan.stages[plan.stages.indexOf(s)-1];return s.target-before.target;}),[6,6,6,6]);assert.equal(plan.pendingRetractDegrees,6);assert.equal(plan.grossDegrees,4*doseDegrees+42);assert.equal(plan.endB,start.B-4*doseDegrees+6);}const r={...recipe,doseDegrees:90,retractDegrees:6,retractPercent:0,retractEachPad:false},plan=P.plan(['R1'],r,q,start,0,0);assert.equal(plan.pendingRetractDegrees,6);assert.equal(plan.grossDegrees,186);const conditioner=P.plan(['R1'],{...r,doseDegrees:.25,retractDegrees:0},q,start,0,0);assert.equal(conditioner.pendingRetractDegrees,0);assert.equal(conditioner.stages.filter(s=>s.tag==='inter-resistor-retract').length,0);for(const retractDegrees of [-.01,6.001,45.01])assert.throws(()=>P.validateRecipe({...r,retractDegrees},q),/Absolute retract/);}

{const r={id:'r',sessionId:'s',startedAt:'2026-10-03T00:00:00Z',status:'completed-awaiting-operator-inspection',reservedGrossDegrees:20,stages:[{axis:'B',tag:'inter-resistor-retract',verified:true,startRaw:{B:0},reportedRaw:{B:10},finishedAt:'2026-10-03T00:00:01Z'},{axis:'B',tag:'restore-prior-inter-resistor-retract',verified:true,startRaw:{B:10},reportedRaw:{B:0},startedAt:'2026-10-03T00:00:02Z'}]},pair={reverse:{recordId:'r',stageIndex:0},restore:{recordId:'r',stageIndex:1},matchedDegrees:10},a={scope:'offline-recent-verified-retraction-cycle-audit',pairs:[pair],grossClosedCycleDegrees:20},entries=[{id:'r',status:'verified',plannedGrossDegrees:20}];assert.equal(P.validateClosedCycleCredit(a,{r},entries,'s'),20);assert.throws(()=>P.validateClosedCycleCredit({...a,pairs:[pair,pair]},{r},entries,'s'),/Duplicate/);assert.throws(()=>P.validateClosedCycleCredit({...a,grossClosedCycleDegrees:150},{r},entries,'s'),/credit/);assert.throws(()=>P.validateClosedCycleCredit({...a,grossClosedCycleDegrees:NaN},{r},entries,'s'),/finite/);r.startedAt='2026-10-02T22:00:00Z';assert.throws(()=>P.validateClosedCycleCredit(a,{r},entries,'s'),/completely verified/);r.startedAt='2026-10-03T00:00:00Z';r.stages[1].verified=false;assert.throws(()=>P.validateClosedCycleCredit(a,{r},entries,'s'),/Incomplete/);const budget={maximumAdditionalGrossDegrees:23950},e={planningRemainingMm:19.6737783,mmPerMotorDegreeNominal:.0008246527777777778};assert.throws(()=>P.validateRodCapacity(budget,e),/capacity/);assert(P.validateRodCapacity(budget,e,154).plannedTravelMm<e.planningRemainingMm);}

{const e={planningRemainingMm:19.6737783,mmPerMotorDegreeNominal:.0008246527777777778};assert(P.validateRodCapacity({maximumAdditionalGrossDegrees:24080},e,293.2).plannedTravelMm<e.planningRemainingMm);assert.throws(()=>P.validateRodCapacity({maximumAdditionalGrossDegrees:24201},e,293.2),/capacity/);assert.throws(()=>P.validateRodCapacity({maximumAdditionalGrossDegrees:24080},e,365),/capacity/);}

{const e={planningRemainingMm:19.6737783,mmPerMotorDegreeNominal:.0008246527777777778};assert(P.validateRodCapacity({maximumAdditionalGrossDegrees:24200},e,364.8).plannedTravelMm<e.planningRemainingMm);assert.throws(()=>P.validateRodCapacity({maximumAdditionalGrossDegrees:24200},e,293.2),/capacity/);}
