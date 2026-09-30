/* ES5 policy for staged single waste-prime increments; no hardware. */
(function(root){
'use strict';
function fail(message){throw Error(message);}
function finite(n,label){if(typeof n!=='number'||!isFinite(n))fail(label+' must be finite');return n;}
function text(s,label){if(typeof s!=='string'||!s.trim())fail(label+' required');}
function close(a,b,tolerance,label){if(Math.abs(finite(a,label)-finite(b,label))>tolerance)fail(label+' mismatch');}
function step(q){
 if(!q||q.schema!==1||q.scope!=='single-negative-raw-B-waste-prime')fail('Restricted waste-prime request required');
 if(q.axis!=='B'||finite(q.deltaDegrees,'deltaDegrees')!==-20)fail('Waste prime requires exactly minus20 degrees');
 if(Object.keys(q).some(function(k){return /^(deltaMm|deltaB|target|axes|command|gcode)$/.test(k);}))fail('Ambiguous motion input');
 return {axis:'B',deltaDegrees:-20};
}
function validate(q,now,jvm){
 step(q);var uuid=/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/;
 if(!uuid.test(q.id)||!uuid.test(q.sessionId)||q.jvmStartMs!==jvm)fail('Exact request/session/JVM required');
 if(!finite(q.createdMs,'createdMs')||q.createdMs>now||now-q.createdMs>300000)fail('Stale/future request');
 text(q.operator,'operator');if(q.speedFraction!==.05)fail('Reviewed native minimum fraction required');
 ['operatorVerifiedReceiver','bothHeadsClear','motionAreaClear','reviewedNegativeBWastePrime'].forEach(function(k){if(q[k]!==true)fail(k+' required');});
 if(!/^[a-f0-9]{64}$/.test(q.liveConfigurationSha256))fail('Exact live configuration hash required');
 ['barrierEvidence','profileEvidence','configurationEvidence','corridorEvidence','homeEvidence','initialAccountingEvidence','nativePreviewEvidence'].forEach(function(k){var e=q[k];if(!e||typeof e.path!=='string'||e.path.charAt(0)!=='/'||!/^[a-f0-9]{64}$/.test(e.sha256))fail(k+' exact file/hash required');});
 finite(q.corridorEvidence.capturedMs,'image time');if(q.corridorEvidence.capturedMs>q.createdMs||now-q.corridorEvidence.capturedMs>300000)fail('Fresh reviewed image required');
 ['expectedRaw','expectedDriver'].forEach(function(k){if(!q[k]||Object.keys(q[k]).sort().join(',')!=='A,B,X,Y,Z')fail('Five axes required');Object.keys(q[k]).forEach(function(a){finite(q[k][a],k+a);});});
 if(!q.expectedNativePoses||Object.keys(q.expectedNativePoses).sort().join(',')!=='N1,N2,bottom,top')fail('Four native poses required');
 Object.keys(q.expectedNativePoses).forEach(function(k){['x','y','z','rotation'].forEach(function(a){finite(q.expectedNativePoses[k][a],k+a);});});
 if(q.previousLedgerSha256!==null&&!/^[a-f0-9]{64}$/.test(q.previousLedgerSha256))fail('Explicit previous ledger hash or null required');
 evidence(q.observationEvidence,'observation evidence',q.previousLedgerSha256===null);text(q.installedNeedleId,'installed needle');if(q.noHomeOrReceiverOrNeedleChangeSinceMeasurement!==true)fail('Unchanged measurement conditions required');expanded(q.expectedExpandedCommands,q.expectedRaw.B-20);return q;
}
function profile(p,q){
 if(!p||p.schema!==1||p.scope!=='measured-receiving-surface-for-waste-prime'||p.measured!==true||p.sessionId!==q.sessionId||p.jvmStartMs!==q.jvmStartMs||p.liveConfigurationSha256!==q.liveConfigurationSha256)fail('Measured same-session receiver profile required');
 if(p.surfaceIdentityVerified!==true||p.bothHeadsClear!==true||p.installedNeedleVerified!==true||p.receiverRestrained!==true)fail('Receiver/needle/clearance evidence incomplete');
 text(p.measurementRecord,'measurement record');if(!p.measurementEvidence||typeof p.measurementEvidence.path!=='string'||p.measurementEvidence.path.charAt(0)!=='/'||!/^[a-f0-9]{64}$/.test(p.measurementEvidence.sha256))fail('Hashed measured receiver evidence required');text(p.receiverId,'receiver ID');
 ['X','Y','Z','A'].forEach(function(a){close(p.rawPose[a],q.expectedRaw[a],.0001,'measured receiver pose '+a);});
 if(p.measurementAxis!=='physical-height-up-mm')fail('Common measured physical height frame required');close(finite(p.measuredTipHeightMm,'measured tip height')-finite(p.measuredReceiverHeightMm,'measured receiver height'),p.measuredTipGapMm,.0001,'measured height difference');
 var gap=finite(p.measuredTipGapMm,'measured gap'),uncertainty=finite(p.gapUncertaintyMm,'gap uncertainty'),low=finite(p.reviewedMinimumGapMm,'minimum gap'),high=finite(p.reviewedMaximumGapMm,'maximum gap');
 if(low<1||gap-uncertainty<1||high<=low||uncertainty<0||gap-uncertainty<low||gap+uncertainty>high)fail('Measured gap including uncertainty outside reviewed noncontact interval');
 if(!NumberIsInteger(p.maximumCumulativeDegrees)||p.maximumCumulativeDegrees<20||p.maximumCumulativeDegrees>300)fail('Explicit session budget20..300 degrees required');
 finite(p.initialB,'initial B');text(p.installedNeedleId,'profile needle');if(p.installedNeedleId!==q.installedNeedleId||p.homeSha256!==q.homeEvidence.sha256||p.initialAccountingSha256!==q.initialAccountingEvidence.sha256)fail('Needle/home/accounting identity changed');if(!NumberIsInteger(p.priorChargedDegrees)||p.priorChargedDegrees<0||p.priorChargedDegrees>10)fail('Explicit prior charged direction-test degrees required');if(p.controllerBStepsPerUnit!==4.44||p.controllerRounding!=='float32-lround-away-from-zero')fail('Audited firmware count rule required');if(p.flowCalibrated!==false)fail('Waste prime must not claim calibrated flow');return p;
}
function NumberIsInteger(n){return typeof n==='number'&&isFinite(n)&&Math.floor(n)===n;}
function evidence(e,label,nullable){if(nullable&&e===null)return;if(!e||typeof e.path!=='string'||e.path.charAt(0)!=='/'||!/^[a-f0-9]{64}$/.test(e.sha256))fail(label+' exact path/hash required');}
function expanded(lines,targetB){if(!Array.isArray(lines)||lines.length<1||lines.length>2)fail('Exact expanded native command trace required');var move=lines[lines.length-1].match(/^G1 B(-?\d+\.\d{4}) F(\d+)$/);if(!move||Number(move[1])!==targetB||Number(move[2])<=0||Number(move[2])>300)fail('Literal B-only positive bounded feed required');if(lines.length===2&&!/^M204 S(?:[1-9]\d*)$/.test(lines[0]))fail('Only optional native acceleration and B move allowed');if(lines.length===2&&Number(lines[0].slice(6))>500)fail('Expanded acceleration exceeds ceiling');return lines;}
function nativePreview(v,q,now){if(!v||v.scope!=='model-only-waste-prime-native-preview'||v.status!=='completed-model-only-native-preview'||v.noControllerAccess!==true||v.noMotion!==true||v.jvmStartMs!==q.jvmStartMs||v.liveConfigurationSha256!==q.liveConfigurationSha256||!v.formatter||v.formatter.scope!=='disconnected-native-GcodeDriver-moveTo-formatter'||v.formatter.transportCalls!==0||v.formatter.sendOnChangeCacheCopied!==true||v.formatter.allMutableMotionObjectsDetached!==true)fail('Actual same-model disconnected native preview required');var t=Date.parse(v.finishedAt);if(!isFinite(t)||t>q.createdMs||now-t>300000)fail('Native preview stale/future');compareExact(v.before.raw,q.expectedRaw,'preview raw');compareExact(v.before.driver,q.expectedDriver,'preview driver');compareExact(v.after.raw,q.expectedRaw,'preview unchanged raw');compareExact(v.after.driver,q.expectedDriver,'preview unchanged driver');compareExact(v.target,target(q.expectedRaw,q),'preview target');expanded(v.formatter.expandedCommands,q.expectedRaw.B-20);if(JSON.stringify(v.formatter.expandedCommands)!==JSON.stringify(q.expectedExpandedCommands))fail('Reviewed native expansion changed');}
function accounting(a,p,q){if(!a||a.schema!==1||a.scope!=='reviewed-waste-prime-displacement-origin'||a.sessionId!==q.sessionId||a.syringeId!==p.syringeId||a.initialB!==p.initialB||a.priorChargedDegrees!==p.priorChargedDegrees||a.noUnaccountedDispense!==true)fail('Complete syringe displacement origin required');text(p.syringeId,'syringe identity');if(p.priorChargedDegrees===0){if(a.noPriorDispenseSinceSyringeInstalled!==true)fail('Zero-charge origin requires explicit no-prior-dispense evidence');}else evidence(a.priorDirectionLedgerEvidence,'prior direction ledger');}
function priorDirectionLedger(l,p){if(!l||l.schema!==1||l.status!=='verified'||l.initialB!==p.initialB||l.reservedDegrees!==p.priorChargedDegrees||!Array.isArray(l.entries)||l.entries.length!==p.priorChargedDegrees||l.entries.some(function(e,i){return e.status!=='verified'||e.reservedDegrees!==1||e.startB!==p.initialB-i||e.targetB!==p.initialB-i-1;}))fail('Prior displacement not completely charged');}
function observation(o,previousReport,previous,q,now){if(!o||o.schema!==1||o.scope!=='reviewed-waste-prime-outlet-and-receiver'||o.previousRequestId!==previous.requestId||o.sessionId!==q.sessionId||o.profileSha256!==q.profileEvidence.sha256||o.liveConfigurationSha256!==q.liveConfigurationSha256||o.jvmStartMs!==q.jvmStartMs||o.outletAndReceiverReviewed!==true||['no-visible-paste','emerging-not-consistent'].indexOf(o.result)<0)fail('Fresh continuing physical observation required; consistent/abnormal stops');text(o.operator,'observation operator');var t=finite(o.reviewedMs,'observation time');if(t>q.createdMs||now-t>300000)fail('Observation stale/future');evidence(o.previousReportEvidence,'previous terminal report');if(!previousReport||previousReport.id!==previous.requestId||previousReport.status!=='completed-waste-prime-awaiting-observation'||previousReport.controllerPositionVerified!==true||previousReport.countsVerified!==true||previousReport.uncertainCompletion!==false||previousReport.request.sessionId!==q.sessionId||previousReport.request.profileEvidence.sha256!==q.profileEvidence.sha256)fail('Previous increment not terminal verified');var done=Date.parse(previousReport.finishedAt);if(!isFinite(done)||t<done)fail('Observation must follow previous completion');if(!Array.isArray(o.images)||o.images.length<1)fail('New outlet/receiver images required');o.images.forEach(function(e){evidence(e,'observation image');finite(e.capturedMs,'observation image time');if(e.capturedMs<done||e.capturedMs>t||now-e.capturedMs>300000)fail('Fresh post-increment image required');});return o;}
function reserve(old,q,p){
 profile(p,q);var ledger=old?JSON.parse(JSON.stringify(old)):{schema:2,sessionId:q.sessionId,profileSha256:q.profileEvidence.sha256,liveConfigurationSha256:q.liveConfigurationSha256,jvmStartMs:q.jvmStartMs,initialB:p.initialB,priorChargedDegrees:p.priorChargedDegrees,initialAccountingSha256:p.initialAccountingSha256,lastVerifiedB:p.initialB-p.priorChargedDegrees,reservedDegrees:p.priorChargedDegrees,status:'verified',entries:[]};
 if((old===null)!==(q.previousLedgerSha256===null))fail('Ledger origin/previous hash mismatch');
 if(ledger.schema!==2||ledger.sessionId!==q.sessionId||ledger.profileSha256!==q.profileEvidence.sha256||ledger.liveConfigurationSha256!==q.liveConfigurationSha256||ledger.jvmStartMs!==q.jvmStartMs||ledger.initialB!==p.initialB||ledger.priorChargedDegrees!==p.priorChargedDegrees||ledger.initialAccountingSha256!==p.initialAccountingSha256||ledger.status!=='verified'||!Array.isArray(ledger.entries))fail('Ledger identity or previous completion not verified');
 var sum=p.priorChargedDegrees,seen={};ledger.entries.forEach(function(e){if(typeof e.requestId!=='string'||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(e.requestId)||seen[e.requestId]||e.requestId===q.id||e.status!=='verified'||e.reservedDegrees!==20)fail('Malformed/repeated/pending ledger entry');seen[e.requestId]=true;close(e.startB,p.initialB-sum,.0001,'historical start B');sum+=20;close(e.targetB,p.initialB-sum,.0001,'historical target B');});
 if(!NumberIsInteger(ledger.reservedDegrees)||ledger.reservedDegrees!==sum)fail('Ledger reservation sum corrupted');
 close(ledger.lastVerifiedB,p.initialB-sum,.0001,'ledger cumulative B');close(q.expectedRaw.B,ledger.lastVerifiedB,.0001,'next B start');close(q.expectedDriver.B,ledger.lastVerifiedB,.0001,'next driver B start');
 if(old&&q.observationEvidence===null)fail('Continuation observation required');if(sum+20>p.maximumCumulativeDegrees)fail('Cumulative B budget exhausted');
 ledger.reservedDegrees=sum+20;ledger.status='reserved';ledger.entries.push({requestId:q.id,startB:q.expectedRaw.B,targetB:p.initialB-ledger.reservedDegrees,reservedDegrees:20,status:'reserved',observationEvidence:q.observationEvidence,previousLedgerSha256:q.previousLedgerSha256});return ledger;
}
function finish(ledger,q,success){var l=JSON.parse(JSON.stringify(ledger)),e=l.entries[l.entries.length-1];if(l.status!=='reserved'||!e||e.requestId!==q.id)fail('Unknown reserved prime increment');l.status=success?'verified':'faulted';e.status=l.status;if(success)l.lastVerifiedB=e.targetB;return l;}
function countB(b){var f=new Float32Array(1);f[0]=b;var x=f[0];f[0]=4.44;x*=f[0];f[0]=x;x=f[0];return x<0?-Math.floor(-x+.5):Math.floor(x+.5);}
function fullResponse(lines,reported,expected){var reports=[],counts=[],positionIndex=-1;lines.forEach(function(line,i){if(/error\s*:|!!|\bstart\b|resend|reset|disconnect|unknown command|halted|fatal|\bkilled\b/i.test(line))fail('Fault in full response');var m=String(line).match(/^X:(-?\d+\.\d+) Y:(-?\d+\.\d+) Z:(-?\d+\.\d+) A:(-?\d+\.\d+) B:(-?\d+\.\d+) Count X:(-?\d+) Y:(-?\d+) Z:(-?\d+) A:(-?\d+) B:(-?\d+)$/);if(m){var r={},c={};['X','Y','Z','A','B'].forEach(function(k,j){r[k]=Number(m[j+1]);c[k]=Number(m[j+6]);if(!NumberIsInteger(c[k])||Math.abs(c[k])>9007199254740991)fail('Unsafe controller count');});reports.push(r);counts.push(c);positionIndex=i;}else if(/\b[XYZAB]:/.test(line))fail('Malformed position/count response');});if(reports.length!==1||!lines.slice(positionIndex+1).some(function(line){return /^ok/.test(line);}))fail('Exactly one full position/count report with following ACK required');compareReported(reported,expected,expected);compareExact(reports[0],reported,'full response/native report');if(counts[0].B!==countB(expected.B))fail('Absolute B controller count mismatch');return counts[0];}
function countsStep(before,after,q){['X','Y','Z','A'].forEach(function(k){if(before[k]!==after[k])fail('Unexpected non-B controller count change');});if(before.B!==countB(q.expectedRaw.B)||after.B!==countB(q.expectedRaw.B-20))fail('Wrong absolute B controller counts');}

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
function target(raw,q){var move=step(q),result={};['X','Y','Z','A','B'].forEach(function(a){result[a]=finite(raw[a],a)+(a===move.axis?move.deltaDegrees:0);});return result;}
function compareNativeStep(before,after,q,tolerance){
 var deltaB=step(q).deltaDegrees;
 ['N1','N2','top','bottom'].forEach(function(k){['x','y','z','rotation'].forEach(function(a){var delta=a==='rotation'&&k==='N2'?deltaB:0;close(after[k][a],before[k][a]+delta,typeof tolerance==='number'?tolerance:(a==='rotation'?0.3:0.02),'native polarity '+k+' '+a);});});
}
function compareExact(actual,expected,label){['X','Y','Z','A','B'].forEach(function(a){close(actual[a],expected[a],0.0001,label+' '+a);});}
function barrier(record,q,now){
 if(!record||record.status!=='completed-read-only-position-barrier'||record.noMotionCommandSubmitted!==true||record.controllerPositionVerified!==true||record.uncertainCompletion!==false||!record.request||record.request.jvmStartMs!==q.jvmStartMs||record.liveConfigurationSha256!==q.liveConfigurationSha256||record.request.liveConfigurationSha256!==q.liveConfigurationSha256)fail('Successful same-JVM/config position barrier required');
 var done=Date.parse(record.finishedAt);if(!isFinite(done)||done>q.createdMs||now-done>300000)fail('Position barrier stale/future');
 var state=record.afterQuerySnapshot;if(!state||!state.nativePoses)fail('Barrier snapshots missing');compareExact(state.raw,q.expectedRaw,'barrier raw');compareExact(state.driver,q.expectedDriver,'barrier driver');
 ['N1','N2','top','bottom'].forEach(function(k){['x','y','z','rotation'].forEach(function(a){close(state.nativePoses[k][a],q.expectedNativePoses[k][a],0.0001,'barrier native '+k+' '+a);});});
 compareReported(record.reported,state.raw,state.driver);
}
var api={nativePreview:nativePreview,expanded:expanded,accounting:accounting,priorDirectionLedger:priorDirectionLedger,observation:observation,countB:countB,fullResponse:fullResponse,countsStep:countsStep,profile:profile,reserve:reserve,finish:finish,barrier:barrier,compareNativeStep:compareNativeStep,step:step,validate:validate,close:close,compareReported:compareReported,target:target,compareExact:compareExact,comparePostModel:comparePostModel,compareFirmwareStep:compareFirmwareStep};if(typeof module!=='undefined')module.exports=api;else root.PasteWastePrime=api;
})(this);
