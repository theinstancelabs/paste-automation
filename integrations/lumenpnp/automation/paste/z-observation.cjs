/* Narrow ES5 contract for the single-step Z observer. No hardware. */
(function(root){
'use strict';
function fail(message){throw Error(message);}
function finite(n,label){if(typeof n!=='number'||!isFinite(n))fail(label+' must be finite');return n;}
function text(s,label){if(typeof s!=='string'||!s.trim())fail(label+' required');}
function close(a,b,tolerance,label){if(Math.abs(finite(a,label)-finite(b,label))>tolerance)fail(label+' mismatch');}
function step(q){
 if(!q||q.schema!==2||q.scope!=='bounded-signed-raw-Z-observation')fail('Restricted raw Z observation required');
 Object.keys(q).forEach(function(k){if((/^delta/i.test(k)||k==='axis'||k==='axes'||k==='target'||k==='targetRaw')&&['axis','deltaMm'].indexOf(k)<0)fail('Ambiguous motion fields');});
 if(q.axis!=='Z'||[-5,-1,1,5].indexOf(finite(q.deltaMm,'deltaMm'))<0)fail('Only discrete signed 1 or 5 mm raw Z steps allowed');
 return {axis:'Z',deltaMm:q.deltaMm};
}
function validate(q,now,jvm){
 if(!q)fail('Restricted survey request required');step(q);
 if(typeof q.id!=='string'||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(q.id))fail('Fresh survey UUID required');
 finite(q.createdMs,'createdMs');if(q.createdMs>now||now-q.createdMs>300000||q.jvmStartMs!==jvm)fail('Stale or different JVM survey request');
 if(q.speedFraction!==0.05||q.speedOverPrecision!==true)fail('Native speed fraction 0.05 with audited backlash bypass required');
 text(q.operator,'operator');if(typeof q.liveConfigurationSha256!=='string'||!/^[a-f0-9]{64}$/.test(q.liveConfigurationSha256))fail('Exact live configuration SHA256 required');
 ['operatorVerifiedJointZStep','bothHeadsClearAlongStep','motionAreaClear','noHeldPartsObserved'].forEach(function(k){if(q[k]!==true)fail(k+' attestation required');});
 if(!q.corridorEvidence||typeof q.corridorEvidence.path!=='string'||q.corridorEvidence.path.charAt(0)!=='/'||!/^[a-f0-9]{64}$/.test(q.corridorEvidence.sha256))fail('Reviewed corridor image path and SHA256 required');
 finite(q.corridorEvidence.capturedMs,'corridor capturedMs');if(q.corridorEvidence.capturedMs>q.createdMs||now-q.corridorEvidence.capturedMs>300000)fail('Reviewed corridor image stale/future');
 ['expectedRaw','expectedDriver'].forEach(function(k){if(!q[k]||Object.keys(q[k]).sort().join(',')!=='A,B,X,Y,Z')fail('Exact five-axis snapshot required');Object.keys(q[k]).forEach(function(a){finite(q[k][a],k+' '+a);});});
 if(!q.barrierEvidence||typeof q.barrierEvidence.path!=='string'||q.barrierEvidence.path.charAt(0)!=='/'||!/^[a-f0-9]{64}$/.test(q.barrierEvidence.sha256))fail('Successful position barrier path/hash required');
 if(!q.expectedNativePoses)fail('Expected native poses required');
 ['N1','N2','top','bottom'].forEach(function(k){if(!q.expectedNativePoses[k])fail('Missing '+k+' pose');['x','y','z','rotation'].forEach(function(a){finite(q.expectedNativePoses[k][a],k+' '+a);});});
 if(!q.jointInterval||q.jointInterval.reviewedForCurrentPose!==true)fail('Explicit current-pose local interval review required');
 text(q.jointInterval.reviewRecord,'joint interval review record');
 var z=q.expectedRaw.Z,end=z+q.deltaMm;close(q.jointInterval.minRawZ,Math.min(z,end),1e-9,'exact reviewed segment minimum');close(q.jointInterval.maxRawZ,Math.max(z,end),1e-9,'exact reviewed segment maximum');
 nativeConfiguration(q.nativeZConfiguration,q);
 return q;
}
function compareReported(reported,savedRaw,savedDriver){
 if(!reported||Object.keys(reported).sort().join(',')!=='A,B,X,Y,Z')fail('Incomplete five-axis M114 report');
 ['X','Y','Z','A','B'].forEach(function(a){var tolerance=(a==='A'||a==='B')?0.3:0.02;close(reported[a],savedRaw[a],tolerance,'reported/model '+a);close(reported[a],savedDriver[a],tolerance,'reported/pre-query-driver '+a);});
}
// Model coordinates can synchronize to the firmware's rounded report during
// native completion. This tolerance applies ONLY after the one-axis command;
// exact request/start validation remains separate and unchanged.
function comparePostModel(actual,expected){
 ['actual','expected'].forEach(function(k){var v=k==='actual'?actual:expected;if(!v||Object.keys(v).sort().join(',')!=='A,B,X,Y,Z')fail('Complete five-axis postmove snapshot required');});
 ['X','Y','Z','A','B'].forEach(function(a){close(actual[a],expected[a],(a==='A'||a==='B')?0.3:0.02,'postmove model '+a);});
}
function compareFirmwareStep(before,after,q){
 if(!before||!after||Object.keys(before).sort().join(',')!=='A,B,X,Y,Z'||Object.keys(after).sort().join(',')!=='A,B,X,Y,Z')fail('Independent before/after firmware reports required');
 var expected=target(before,q);
 ['X','Y','Z','A','B'].forEach(function(a){close(after[a],expected[a],(a==='A'||a==='B')?0.3:0.02,'firmware before/after '+a);});
}
function target(raw,q){var move=step(q),result={};['X','Y','Z','A','B'].forEach(function(a){result[a]=finite(raw[a],a)+(a===move.axis?move.deltaMm:0);});return result;}
function compareNativeStep(before,after,q,tolerance){
 var dz=step(q).deltaMm;
 ['N1','N2','top','bottom'].forEach(function(k){['x','y','z','rotation'].forEach(function(a){var delta=a==='z'?(k==='N1'?dz:k==='N2'?-dz:0):0;close(after[k][a],before[k][a]+delta,typeof tolerance==='number'?tolerance:(a==='rotation'?0.3:0.02),'native polarity '+k+' '+a);});});
}
function compareExact(actual,expected,label){['X','Y','Z','A','B'].forEach(function(a){close(actual[a],expected[a],0.0001,label+' '+a);});}
function nativeConfiguration(actual,q){
 var expected=q.nativeZConfiguration,keys=['softLowEnabled','softLowMm','softHighEnabled','softHighMm','safeLowEnabled','safeLowMm','safeHighEnabled','safeHighMm'];
 [actual,expected].forEach(function(c){if(!c||Object.keys(c).sort().join(',')!==keys.slice().sort().join(','))fail('Exact native Z limit snapshot required');keys.forEach(function(k){if(/Enabled$/.test(k)){if(typeof c[k]!=='boolean')fail('Native limit flag must be boolean');}else finite(c[k],k);});});
 keys.forEach(function(k){if(actual[k]!==expected[k])fail('Native Z configuration changed: '+k);});
 var low=Math.min(q.expectedRaw.Z,q.expectedRaw.Z+q.deltaMm),high=Math.max(q.expectedRaw.Z,q.expectedRaw.Z+q.deltaMm);
 if(actual.softLowEnabled&&low<actual.softLowMm||actual.softHighEnabled&&high>actual.softHighMm)fail('Step outside enabled native soft limits');
}
function barrier(record,q,now){
 if(!record||record.status!=='completed-read-only-position-barrier'||record.noMotionCommandSubmitted!==true||record.controllerPositionVerified!==true||record.uncertainCompletion!==false||!record.request||record.request.jvmStartMs!==q.jvmStartMs||record.liveConfigurationSha256!==q.liveConfigurationSha256||record.request.liveConfigurationSha256!==q.liveConfigurationSha256)fail('Successful same-JVM/config position barrier required');
 var done=Date.parse(record.finishedAt);if(!isFinite(done)||done>q.createdMs||now-done>300000)fail('Position barrier stale/future');
 var state=record.afterQuerySnapshot;if(!state||!state.nativePoses)fail('Barrier snapshots missing');compareExact(state.raw,q.expectedRaw,'barrier raw');compareExact(state.driver,q.expectedDriver,'barrier driver');
 ['N1','N2','top','bottom'].forEach(function(k){['x','y','z','rotation'].forEach(function(a){close(state.nativePoses[k][a],q.expectedNativePoses[k][a],0.0001,'barrier native '+k+' '+a);});});
 compareReported(record.reported,state.raw,state.driver);
}
var api={nativeConfiguration:nativeConfiguration,barrier:barrier,compareNativeStep:compareNativeStep,step:step,validate:validate,close:close,compareReported:compareReported,target:target,compareExact:compareExact,comparePostModel:comparePostModel,compareFirmwareStep:compareFirmwareStep};if(typeof module!=='undefined')module.exports=api;else root.PasteZObservation=api;
})(this);
