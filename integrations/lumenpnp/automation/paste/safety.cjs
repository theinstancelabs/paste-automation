/* ES5 to share offline tests and the installed OpenPnP Nashorn runtime. */
(function(root){
'use strict';
function fail(message){throw new Error(message);}
function finite(v,label){if(typeof v!=='number'||!isFinite(v))fail(label+' must be measured finite number');return v;}
function text(v,label){if(typeof v!=='string'||!v.trim())fail(label+' evidence required');}
function near(a,b,label){if(Math.abs(finite(a,label)-finite(b,label))>0.001)fail(label+' changed');}
function bound(v,lo,hi,label){finite(v,label);finite(lo,label);finite(hi,label);if(lo>=hi||v<lo||v>hi)fail(label+' outside measured bounds');}
function profile(p){
 if(!p||p.calibrated!==true||p.nativeCoordinateFrame!=='openpnp-N2-mm')fail('Measured OpenPnP N2 profile required');
 ['measurementRecord','registrationRecord','jointClearanceRecord','configurationBackup','firmwareSettingsRecord','nativeSpeedRecord'].forEach(function(k){text(p[k],k);});
 ['x','y','z'].forEach(function(a){finite(p[a+'Min'],a);finite(p[a+'Max'],a);if(p[a+'Min']>=p[a+'Max'])fail(a+' bounds invalid');});
 bound(p.safeZ,p.zMin,p.zMax,'right clearance');finite(p.leftClearanceZ,'left clearance');
 if(['increasing','decreasing'].indexOf(p.clearanceDirection)<0)fail('clearance direction required');
 ['travelFeed','zFeed','dispenseFeed'].forEach(function(k){if(finite(p[k],k)<=0)fail(k+' must be positive');});
 if(finite(p.speedFraction,'native speed')<=0||p.speedFraction>0.1)fail('First native air commissioning speed must be >0 and <=0.1');
 if(!p.rawBounds||Object.keys(p.rawBounds).length<2)fail('Measured controller-axis bounds required');
 Object.keys(p.rawBounds).forEach(function(k){var b=p.rawBounds[k];if(!b||finite(b.min,k)>=finite(b.max,k))fail('raw bounds invalid');});
 text(p.leftNozzleId,'left nozzle id');text(p.rightNozzleId,'right nozzle id');
 if(p.leftNozzleId===p.rightNozzleId)fail('Distinct left/right nozzles required');
 text(p.leftHeadOffsets,'left head offsets');text(p.rightHeadOffsets,'right head offsets');
 if(typeof p.liveConfigurationSha256!=='string'||!/^[a-f0-9]{64}$/.test(p.liveConfigurationSha256))fail('Measured live configuration SHA256 required');
}
function plan(b){
 if(!b||b.schema!==1||b.mode!=='air'||b.coordinateFrame!=='openpnp-N2-mm')fail('Air-only native plan required');
 if(typeof b.id!=='string'||!/^[a-f0-9-]{36}$/.test(b.id))fail('Invalid one-shot plan id');
 profile(b.profile);
 if(!b.provenance||b.provenance.forkCommit!=='c497bfbef2f7347538966c129bf7ac7bdc2c1a0f')fail('Unpinned planner');
 if(!b.points||!b.points.length||b.points.length>10000)fail('Bounded nonempty point list required');
 if(!b.job||b.job.coordinateFrame!=='machine'||!b.job.placements||b.job.placements.length!==b.points.length)fail('Measured job snapshot required');
 ['preGcode','postGcode'].forEach(function(k){if(b.job[k]!==undefined&&(typeof b.job[k]!=='string'||b.job[k].trim()))fail('Raw G-code forbidden');});
 b.points.forEach(function(pt,i){bound(pt.x,b.profile.xMin,b.profile.xMax,'X');bound(pt.y,b.profile.yMin,b.profile.yMax,'Y');
   near(pt.x,b.job.placements[i].x,'job X');near(pt.y,b.job.placements[i].y,'job Y');
   var z=b.job.placements[i].z;bound(z,b.profile.zMin,b.profile.zMax,'dispense Z');
   if((b.profile.clearanceDirection==='decreasing'?z-b.profile.safeZ:b.profile.safeZ-z)<=0)fail('No surface clearance');
 });
}
function session(s,b,hash,now,jvmStart){
 plan(b);
 if(!s||s.planSha256!==hash||s.planId!==b.id)fail('Session does not match exact reviewed plan');
 if(s.jvmStartMs!==jvmStart)fail('Session does not match running OpenPnP');
 if(typeof s.createdMs!=='number'||!isFinite(s.createdMs)||s.createdMs>now||now-s.createdMs>300000)fail('Session attestation expired');
 ['installationComplete','motionAreaClear','bothHeadsClear','homingCurrent','registrationCurrent','supervisorPresent','physicalStopAccessible','rightHeadExcludedFromPlacement','nativeFrameVerified','startPoseCameraVerified'].forEach(function(k){if(s[k]!==true)fail('Current supervised attestation required: '+k);});
 text(s.operator,'operator');text(s.evidenceRecord,'session evidence');
 if(!s.start||!s.start.left||!s.start.right)fail('Exact reviewed start poses required');
 ['left','right'].forEach(function(side){['x','y','z','rotation'].forEach(function(k){finite(s.start[side][k],side+' '+k);});});
 near(s.start.left.z,b.profile.leftClearanceZ,'left clearance');near(s.start.right.z,b.profile.safeZ,'right clearance');
 bound(s.start.right.x,b.profile.xMin,b.profile.xMax,'start X');bound(s.start.right.y,b.profile.yMin,b.profile.yMax,'start Y');
}
var api={profile:profile,plan:plan,session:session,near:near,bound:bound};
if(typeof module!=='undefined')module.exports=api;else root.PasteSafety=api;
})(this);
