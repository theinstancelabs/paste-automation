/* Narrow ES5 contract shared with the staged native camera survey. No hardware. */
(function(root){
'use strict';
function fail(message){throw Error(message);}
function finite(n,label){if(typeof n!=='number'||!isFinite(n))fail(label+' must be finite');return n;}
function text(s,label){if(typeof s!=='string'||!s.trim())fail(label+' required');}
function close(a,b,tolerance,label){if(Math.abs(finite(a,label)-finite(b,label))>tolerance)fail(label+' mismatch');}
function validate(q,now,jvm){
 if(!q||q.schema!==1||q.scope!=='camera-survey-raw-X-plus10-only')fail('Restricted survey request required');
 if(typeof q.id!=='string'||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(q.id))fail('Fresh survey UUID required');
 finite(q.createdMs,'createdMs');if(q.createdMs>now||now-q.createdMs>300000||q.jvmStartMs!==jvm)fail('Stale or different JVM survey request');
 if(q.deltaRawXmm!==10||q.speedFraction!==0.1||q.speedOverPrecision!==true)fail('Only +10 raw X at native speed fraction 0.1 with audited backlash bypass is allowed');
 text(q.operator,'operator');if(typeof q.liveConfigurationSha256!=='string'||!/^[a-f0-9]{64}$/.test(q.liveConfigurationSha256))fail('Exact live configuration SHA256 required');
 ['operatorVerified10mmCorridor','bothHeadsClearAlongCorridor','motionAreaClear','noHeldPartsObserved'].forEach(function(k){if(q[k]!==true)fail(k+' attestation required');});
 if(!q.corridorEvidence||typeof q.corridorEvidence.path!=='string'||q.corridorEvidence.path.charAt(0)!=='/'||!/^[a-f0-9]{64}$/.test(q.corridorEvidence.sha256))fail('Reviewed corridor image path and SHA256 required');
 finite(q.corridorEvidence.capturedMs,'corridor capturedMs');if(q.corridorEvidence.capturedMs>q.createdMs||now-q.corridorEvidence.capturedMs>300000)fail('Reviewed corridor image stale/future');
 ['expectedRaw','expectedDriver'].forEach(function(k){if(!q[k]||Object.keys(q[k]).sort().join(',')!=='A,B,X,Y,Z')fail('Exact five-axis snapshot required');Object.keys(q[k]).forEach(function(a){finite(q[k][a],k+' '+a);});});
 if(!q.expectedNativePoses)fail('Expected native poses required');
 ['N1','N2','top','bottom'].forEach(function(k){if(!q.expectedNativePoses[k])fail('Missing '+k+' pose');['x','y','z','rotation'].forEach(function(a){finite(q.expectedNativePoses[k][a],k+' '+a);});});
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
function compareFirmwareStep(before,after){
 if(!before||!after||Object.keys(before).sort().join(',')!=='A,B,X,Y,Z'||Object.keys(after).sort().join(',')!=='A,B,X,Y,Z')fail('Independent before/after firmware reports required');
 var expected=target(before);
 ['X','Y','Z','A','B'].forEach(function(a){close(after[a],expected[a],(a==='A'||a==='B')?0.3:0.02,'firmware before/after '+a);});
}
function target(raw){var result={};['X','Y','Z','A','B'].forEach(function(a){result[a]=finite(raw[a],a)+(a==='X'?10:0);});return result;}
function compareExact(actual,expected,label){['X','Y','Z','A','B'].forEach(function(a){close(actual[a],expected[a],0.0001,label+' '+a);});}
var api={validate:validate,close:close,compareReported:compareReported,target:target,compareExact:compareExact,comparePostModel:comparePostModel,compareFirmwareStep:compareFirmwareStep};if(typeof module!=='undefined')module.exports=api;else root.PasteSurveyRequest=api;
})(this);
