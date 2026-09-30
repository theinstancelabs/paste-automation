const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const guard=require('./safety.cjs');
// Synthetic values used only by tests; never a calibration record.
function fixture(){
 const profile={calibrated:true,liveConfigurationSha256:'a'.repeat(64),nativeCoordinateFrame:'openpnp-N2-mm',measurementRecord:'synthetic',registrationRecord:'synthetic',jointClearanceRecord:'synthetic',configurationBackup:'synthetic',firmwareSettingsRecord:'synthetic',nativeSpeedRecord:'synthetic',leftNozzleId:'left',rightNozzleId:'right',leftHeadOffsets:'synthetic',rightHeadOffsets:'synthetic',xMin:0,xMax:20,yMin:0,yMax:20,zMin:0,zMax:20,safeZ:15,leftClearanceZ:5,clearanceDirection:'increasing',travelFeed:10,zFeed:10,dispenseFeed:10,speedFraction:0.01,rawBounds:{x:{min:0,max:20},y:{min:0,max:20}}};
 const job={coordinateFrame:'machine',placements:[{x:10,y:10,z:3}],dispenseDegrees:1,retractionDegrees:0,dwellMilliseconds:0};
 const b={schema:1,id:'12345678-1234-1234-1234-123456789abc',mode:'air',coordinateFrame:'openpnp-N2-mm',profile,job,points:[{x:10,y:10}],provenance:{forkCommit:'c497bfbef2f7347538966c129bf7ac7bdc2c1a0f'}};
 const s={planId:b.id,planSha256:'testhash',createdMs:1000,jvmStartMs:1,operator:'synthetic',evidenceRecord:'synthetic',start:{left:{x:1,y:1,z:5,rotation:0},right:{x:2,y:2,z:15,rotation:0}}};
 ['installationComplete','motionAreaClear','bothHeadsClear','homingCurrent','registrationCurrent','supervisorPresent','physicalStopAccessible','rightHeadExcludedFromPlacement','nativeFrameVerified','startPoseCameraVerified'].forEach(k=>s[k]=true);
 return {profile,job,b,s};
}
test('pending profile cannot generate runnable plan',()=>assert.throws(()=>guard.profile(JSON.parse(readFileSync(__dirname+'/right-head-profile.pending.json'))),/Measured/));
test('synthetic air profile and exact session validate',()=>{const {b,s}=fixture();guard.session(s,b,'testhash',1001,1);});
test('reject wet execution and raw insertion',()=>{const {b}=fixture();b.mode='wet';assert.throws(()=>guard.plan(b),/Air-only/);b.mode='air';b.job.preGcode='G28';assert.throws(()=>guard.plan(b),/Raw/);});
test('reject raw/board frame without native registration',()=>{const {b}=fixture();b.coordinateFrame='machine';assert.throws(()=>guard.plan(b));b.coordinateFrame='openpnp-N2-mm';b.job.coordinateFrame='board';assert.throws(()=>guard.plan(b));});
test('bounds validate every point and reject NaN',()=>{const {b}=fixture();b.points.push({x:21,y:10});b.job.placements.push({x:21,y:10,z:3});assert.throws(()=>guard.plan(b),/outside/);b.points[1].x=NaN;assert.throws(()=>guard.plan(b),/finite/);});
test('native speed is separate conservative fraction',()=>{const {profile}=fixture();profile.speedFraction=10;assert.throws(()=>guard.profile(profile),/speed/);});
test('left and right measured joint clearance mandatory',()=>{const {b,s}=fixture();s.start.left.z=6;assert.throws(()=>guard.session(s,b,'testhash',1001,1),/left clearance/);s.start.left.z=5;s.start.right.z=14;assert.throws(()=>guard.session(s,b,'testhash',1001,1),/right clearance/);});
test('start is within entire measured clearance envelope',()=>{const {b,s}=fixture();s.start.right.x=-1;assert.throws(()=>guard.session(s,b,'testhash',1001,1),/start X/);});
test('attestation expires, cannot cross restart or different plan',()=>{const {b,s}=fixture();assert.throws(()=>guard.session(s,b,'testhash',301001,1),/expired/);assert.throws(()=>guard.session(s,b,'testhash',999,1),/expired/);assert.throws(()=>guard.session(s,b,'testhash',1001,2),/running/);assert.throws(()=>guard.session(s,b,'different',1001,1),/exact/);});
test('missing installation/area/guard confirmations fail closed',()=>{for(const key of ['installationComplete','motionAreaClear','rightHeadExcludedFromPlacement']){const {b,s}=fixture();s[key]=false;assert.throws(()=>guard.session(s,b,'testhash',1001,1),new RegExp(key));}});
test('plan job edits or no surface clearance rejected',()=>{const {b}=fixture();b.job.placements[0].x=2;assert.throws(()=>guard.plan(b),/job X/);b.job.placements[0].x=10;b.job.placements[0].z=16;assert.throws(()=>guard.plan(b),/surface/);});
test('adapter runs exact pinned pure planner and no B commands',async()=>{const {prepare}=await import('./prepare-air-plan.mjs');const {job,profile}=fixture();const b=await prepare(job,profile,'/home/lumen/paste-automation');assert.equal(b.summary.dryRun,true);assert.equal(b.summary.totalDispenseDegrees,0);assert.equal(b.points.length,1);assert.ok(b.previewOnlyGcode.every(c=>!/^G(?:1|92).*B/.test(c)));assert.equal(b.coordinateFrame,'openpnp-N2-mm');});
test('adapter rejects unmeasured profile and board coordinate shortcut',async()=>{const {prepare}=await import('./prepare-air-plan.mjs');const {job,profile}=fixture();profile.calibrated=false;await assert.rejects(prepare(job,profile,'/home/lumen/paste-automation'),/Measured/);profile.calibrated=true;job.coordinateFrame='board';await assert.rejects(prepare(job,profile,'/home/lumen/paste-automation'),/Only measured/);});
