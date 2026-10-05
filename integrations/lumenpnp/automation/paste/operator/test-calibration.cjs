'use strict';
const assert=require('node:assert/strict');
const P=require('../operator-console-policy.cjs');
const p={workZ:58.2,gapUncertaintyMm:.3,rawBounds:{X:{min:0,max:100},Y:{min:0,max:100}},pads:{}};
for(const [ref,xy] of Object.entries({R1:[20,20],R15:[60,20],R40:[20,60]}))p.pads[ref]={'1':{cameraXY:xy,tipXY:[xy[0]-1,xy[1]+1],gapAtWorkZ:.5},'2':{cameraXY:[xy[0]+2,xy[1]],tipXY:[xy[0]+1,xy[1]+1],gapAtWorkZ:.5}};
const samples=Object.keys(p.pads).map(ref=>({ref,cameraXY:P.center(p,ref).map((v,i)=>v+(i?2:1))}));
const aligned=P.fitAlignment(samples,p).profile;
assert.deepEqual(aligned.pads.R1['1'].cameraXY,[21,22]);
assert.deepEqual(aligned.pads.R1['1'].tipXY,[20,23]);
assert.deepEqual(p.pads.R1['1'].cameraXY,[20,20]);
assert.throws(()=>P.fitAlignment(samples.slice(0,2),p),/three/);
assert.throws(()=>P.fitAlignment([samples[0],samples[0],samples[2]],p),/Distinct/);
assert.throws(()=>P.fitAlignment(samples.map(s=>({...s,cameraXY:s.cameraXY.map(v=>v+20)})),p),/10 mm/);
assert.throws(()=>P.fitAlignment(samples.map((s,i)=>({...s,cameraXY:[s.cameraXY[0]+(i===1?3:0),s.cameraXY[1]]})),p),/scale/);
const zs=Object.keys(p.pads).map(ref=>({ref,pad:'1',rawZ:57.2,measuredGap:1.5}));
const z=P.fitSurface(zs,aligned).profile;
assert(Math.abs(z.pads.R1['1'].gapAtWorkZ-.5)<1e-10);
assert.equal(z.gapUncertaintyMm,.3);
const shallower=P.fitSurface(zs.map(s=>({...s,measuredGap:1.2})),aligned).profile;
assert.equal(shallower.workZ,58);
assert(Math.abs(shallower.pads.R1['1'].gapAtWorkZ-.4)<1e-8);
assert.throws(()=>P.fitSurface(zs.map(s=>({...s,measuredGap:NaN})),aligned),/finite/);
assert.throws(()=>P.fitSurface(zs.map(s=>({...s,rawZ:59})),aligned),/outside/);
console.log('operator calibration transform, offset, clearance, and invalid-input checks passed');
const pending={...aligned,heightCalibrationPending:true};const calibrated=P.fitSurface(zs,pending).profile;assert.equal(calibrated.heightCalibrationPending,undefined);assert.equal(calibrated.vacuumReference,undefined);

// Deposit-centroid correction changes only tip XY, after the camera alignment
// and height path have been reconstructed; it is bound to this profile/session.
{const base={...aligned,id:'a'.repeat(64),sessionId:'27c1ab29-a268-47d7-8dcf-eaf2a71ade02'};Object.values(base.pads).forEach(ps=>Object.values(ps).forEach(t=>{t.touchRawZ=57.5;}));const correction={profileId:base.id,sessionId:base.sessionId,basis:'repeated-deposit-centroid-offset',deltaRawXY:[.4,-.25],evidence:{path:'/synthetic/deposit-centroids.json',sha256:'f'.repeat(64)}};const fixed=P.applyTipXYCorrection(base,correction);for(const ref of Object.keys(base.pads))for(const pad of ['1','2']){assert.deepEqual(fixed.pads[ref][pad].cameraXY,base.pads[ref][pad].cameraXY);assert.deepEqual(fixed.pads[ref][pad].tipXY,[Math.round((base.pads[ref][pad].tipXY[0]+.4)*100)/100,Math.round((base.pads[ref][pad].tipXY[1]-.25)*100)/100]);assert.equal(fixed.pads[ref][pad].touchRawZ,base.pads[ref][pad].touchRawZ);}assert.throws(()=>P.applyTipXYCorrection(base,{...correction,profileId:'b'.repeat(64)}),/profile\/session/);assert.throws(()=>P.applyTipXYCorrection(base,{...correction,sessionId:'00000000-0000-0000-0000-000000000000'}),/profile\/session/);assert.throws(()=>P.applyTipXYCorrection(base,{...correction,basis:'measured-pad-centers'}),/basis/);assert.throws(()=>P.applyTipXYCorrection(base,{...correction,deltaRawXY:[2,2]}),/2 mm/);assert.throws(()=>P.applyTipXYCorrection(base,{...correction,deltaRawXY:[NaN,0]}),/finite/);assert.throws(()=>P.applyTipXYCorrection(base,{...correction,evidence:{path:'/synthetic/evidence',sha256:'bad'}}),/hash-bound/);const bounded={...base,rawBounds:{...base.rawBounds,X:{min:0,max:20},Y:{min:0,max:100}}};assert.throws(()=>P.applyTipXYCorrection(bounded,{...correction,deltaRawXY:[2,0]}),/raw bounds/);}

const touchProfile={...aligned,workZ:60,heightCalibrationPending:true,rawBounds:{...aligned.rawBounds,Z:{min:32.25,max:60}}};
const touches=Object.keys(touchProfile.pads).map(ref=>({ref,pad:'1',rawZ:57.75+.001*touchProfile.pads[ref]['1'].tipXY[0],operatorConfirmedBarelyTouching:true}));
const touched=P.fitNeedleTouches(touches,touchProfile).profile;
assert.equal(touched.needleTouchCalibrated,true);assert.equal(touched.heightCalibrationPending,undefined);assert.equal(touched.vacuumReference,undefined);
assert(Math.abs(touched.pads.R15['1'].touchRawZ-touched.pads.R1['1'].touchRawZ-.04)<1e-9);
assert.throws(()=>P.fitNeedleTouches(touches.slice(0,2),touchProfile),/three/);
assert.throws(()=>P.fitNeedleTouches(touches.map(t=>({...t,operatorConfirmedBarelyTouching:false})),touchProfile),/confirmation/);
assert.throws(()=>P.fitNeedleTouches(touches.map(t=>({...t,rawZ:60.1})),touchProfile),/55..63/);
const executable={...touched,safeZ:32.25,travelZ:53.45,rodBudget:{maximumAdditionalGrossDegrees:1000}};
const touchRecipe={padMode:'1',doseDegrees:6,retractPercent:15,dwellMs:0,retractDwellMs:0,bSpeedFraction:.05,workZ:60,heightMode:'gap',gapMm:.2};
const touchPlan=P.plan(['R1','R15','R40'],touchRecipe,executable,{X:20,Y:20,Z:32.25,A:200,B:-10},0,0);
let commandedZ=32.25,index=0;for(const stage of touchPlan.stages){if(stage.axis==='Z')commandedZ=stage.target;if(stage.tag==='dose'){const ref=['R1','R15','R40'][index++];assert.equal(commandedZ,Math.round((touched.pads[ref]['1'].touchRawZ-.2)*100)/100);}}assert.equal(index,3);
