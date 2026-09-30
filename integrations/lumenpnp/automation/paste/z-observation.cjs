/* Narrow ES5 contract for the single-step Z observer. No hardware. */
(function(root){
'use strict';
function fail(message){throw Error(message);}
function finite(n,label){if(typeof n!=='number'||!isFinite(n))fail(label+' must be finite');return n;}
function text(s,label){if(typeof s!=='string'||!s.trim())fail(label+' required');}
function close(a,b,tolerance,label){if(Math.abs(finite(a,label)-finite(b,label))>tolerance)fail(label+' mismatch');}
function step(q){
 if(!q||q.schema!==1||q.scope!=='single-positive-raw-Z-observation')fail('Restricted raw Z observation required');
 Object.keys(q).forEach(function(k){if((/^delta/i.test(k)||k==='axis'||k==='axes'||k==='target'||k==='targetRaw')&&['axis','deltaMm'].indexOf(k)<0)fail('Ambiguous motion fields');});
 if(q.axis!=='Z'||finite(q.deltaMm,'deltaMm')!==1)fail('Initial observation requires exactly +1 mm raw Z');
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
 if(!q.jointInterval||finite(q.jointInterval.minRawZ,'reviewed minimum')<26.5||finite(q.jointInterval.maxRawZ,'reviewed maximum')>36.5||q.jointInterval.minRawZ>=q.jointInterval.maxRawZ||q.jointInterval.reviewedForCurrentPose!==true)fail('Explicit current-pose joint interval review required');
 text(q.jointInterval.reviewRecord,'joint interval review record');
 var z=q.expectedRaw.Z,end=z+q.deltaMm;if(z<26.5||end>36.5||z<q.jointInterval.minRawZ||end>q.jointInterval.maxRawZ)fail('Z step outside restricted application interval');
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
function barrier(record,q,now){
 if(!record||record.status!=='completed-read-only-position-barrier'||record.noMotionCommandSubmitted!==true||record.controllerPositionVerified!==true||record.uncertainCompletion!==false||!record.request||record.request.jvmStartMs!==q.jvmStartMs||record.liveConfigurationSha256!==q.liveConfigurationSha256||record.request.liveConfigurationSha256!==q.liveConfigurationSha256)fail('Successful same-JVM/config position barrier required');
 var done=Date.parse(record.finishedAt);if(!isFinite(done)||done>q.createdMs||now-done>300000)fail('Position barrier stale/future');
 var state=record.afterQuerySnapshot;if(!state||!state.nativePoses)fail('Barrier snapshots missing');compareExact(state.raw,q.expectedRaw,'barrier raw');compareExact(state.driver,q.expectedDriver,'barrier driver');
 ['N1','N2','top','bottom'].forEach(function(k){['x','y','z','rotation'].forEach(function(a){close(state.nativePoses[k][a],q.expectedNativePoses[k][a],0.0001,'barrier native '+k+' '+a);});});
 compareReported(record.reported,state.raw,state.driver);
}
var api={barrier:barrier,compareNativeStep:compareNativeStep,step:step,validate:validate,close:close,compareReported:compareReported,target:target,compareExact:compareExact,comparePostModel:comparePostModel,compareFirmwareStep:compareFirmwareStep};if(typeof module!=='undefined')module.exports=api;else root.PasteZObservation=api;
})(this);
