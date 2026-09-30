'use strict';
// Pure policy for a separately reviewed, single raw-B commissioning stroke.
// Kept ES5 for the installed Nashorn runtime. No controller/filesystem access.
(function(root){
var fail=function(s){throw Error(s);},hashPattern=/^[a-f0-9]{64}$/;
var finite=function(v,k){if(typeof v!=='number'||!isFinite(v))fail(k+' must be finite');return v;};
var steps=[2,4,6,20,-2,-4,-6,-20];
function validate(q,now,jvm){
 if(!q||q.schema!==1||q.scope!=='single-signed-raw-B-commissioning-stroke'||q.enabled!==false)fail('Unknown or enabled commissioning request');
 if(!/^[a-f0-9-]{36}$/.test(q.id)||!/^[a-f0-9-]{36}$/.test(q.sessionId)||q.jvmStartMs!==jvm)fail('Exact request/session/JVM required');
 if(q.axis!=='B'||steps.indexOf(q.deltaDegrees)<0||Math.abs(q.deltaDegrees)>20)fail('Only bounded reviewed signed B steps allowed');
 if(q.speedFraction!==0.05)fail('Native fraction must remain the reviewed 0.05');
 if(!hashPattern.test(q.liveConfigurationSha256)||!q.evidence||!Array.isArray(q.evidence)||q.evidence.length<4)fail('Hash-bound config/profile/image/barrier evidence required');
 q.evidence.forEach(function(e){if(!e||typeof e.path!=='string'||e.path.charAt(0)!=='/'||!hashPattern.test(e.sha256))fail('Hash-bound evidence path/hash invalid');});
 if(!q.expectedRaw||!q.expectedDriver||!q.expectedNativePoses)fail('Exact current pose snapshots required');
 if(!isFinite(q.imageCapturedMs)||!isFinite(q.reviewedImageMs)||q.imageCapturedMs>q.reviewedImageMs||q.reviewedImageMs>q.createdMs||q.createdMs-q.reviewedImageMs>300000)fail('Fresh reviewed image timing required');
 if(q.previousLedgerSha256!==null&&(!q.previousReportEvidence||typeof q.previousReportEvidence.path!=='string'||!hashPattern.test(q.previousReportEvidence.sha256)))fail('Previous terminal stroke report required');
 ['X','Y','Z','A','B'].forEach(function(k){finite(q.expectedRaw[k],'raw '+k);finite(q.expectedDriver[k],'driver '+k);});
 var p=q.receivingProfile;if(!p||p.measured!==true||p.flowCalibrated!==false||!hashPattern.test(p.sha256)||finite(p.measuredGapMm,'measured gap')<=0||finite(p.gapUncertaintyMm,'gap uncertainty')<0||finite(p.measuredGapMm-p.gapUncertaintyMm,'minimum gap')<0.1)fail('Signed stroke requires measured noncontact gap with uncertainty lower bound at least 0.1 mm');
 ['X','Y','Z','A'].forEach(function(k){if(!p.rawPose||typeof p.rawPose[k]!=='number'||Math.abs(p.rawPose[k]-q.expectedRaw[k])>0.0001)fail('Measured receiving profile does not bind current fixed '+k);});
 if(q.deltaDegrees>0&&q.clearanceReview!==true)fail('Positive relief requires reviewed clear travel pose');
 if(typeof now!=='number'||!isFinite(now)||q.createdMs>now||now-q.createdMs>300000||now-q.imageCapturedMs>300000)fail('Stale/future request or image');
 return q;
}
function reserve(old,q,carry){
 validate(q,q.createdMs,q.jvmStartMs);
 if(!carry||carry.schema!==1||carry.sessionId!==q.sessionId||carry.syringeId!==q.syringeId||carry.primeLedgerSha256!==q.primeLedgerSha256||carry.priorGrossDegrees!==10940||carry.manualDisplacementUnknown!==true||carry.verifiedPrimeDegrees!==960||carry.startB!==-240||carry.maximumAbsoluteDegrees!==120)fail('Hash-bound prime and prior-syringe carryover required');
 var l=old?JSON.parse(JSON.stringify(old)):{schema:1,scope:'signed-B-commissioning-strokes',sessionId:q.sessionId,syringeId:q.syringeId,primeLedgerSha256:q.primeLedgerSha256,carryoverSha256:q.carryoverSha256,startB:-240,lastVerifiedB:-240,totalAbsoluteDegrees:0,entries:[],status:'verified'};
 if(l.schema!==1||l.scope!=='signed-B-commissioning-strokes'||l.sessionId!==q.sessionId||l.syringeId!==q.syringeId||l.primeLedgerSha256!==q.primeLedgerSha256||l.carryoverSha256!==q.carryoverSha256||l.status!=='verified'||!Array.isArray(l.entries))fail('Commissioning ledger identity/status invalid');
 if(old){if(!hashPattern.test(q.previousLedgerSha256)||old.lastVerifiedB!==q.expectedRaw.B)fail('Previous ledger hash or exact B position mismatch');}
 else if(q.previousLedgerSha256!==null||q.expectedRaw.B!==-240)fail('Initial request must match immutable prime ledger B=-240');
 if(typeof l.totalAbsoluteDegrees!=='number'||!isFinite(l.totalAbsoluteDegrees)||Math.floor(l.totalAbsoluteDegrees)!==l.totalAbsoluteDegrees||l.totalAbsoluteDegrees<0||l.totalAbsoluteDegrees>120||l.startB!==-240||!isFinite(l.lastVerifiedB))fail('Commissioning ledger budget/position malformed');
 var sum=0,at=-240,seen={};l.entries.forEach(function(e){if(!e||typeof e.requestId!=='string'||seen[e.requestId]||e.status!=='verified'||steps.indexOf(e.deltaDegrees)<0||e.startB!==at||e.targetB!==e.startB+e.deltaDegrees||e.absoluteDegrees!==Math.abs(e.deltaDegrees))fail('Commissioning ledger history malformed');seen[e.requestId]=true;sum+=e.absoluteDegrees;at=e.targetB;});
 if(sum!==l.totalAbsoluteDegrees||at!==l.lastVerifiedB||sum>120)fail('Commissioning ledger gross/target chain mismatch');
 if(seen[q.id])fail('Commissioning request replay');
 var next=l.totalAbsoluteDegrees+Math.abs(q.deltaDegrees);if(next>120)fail('Commissioning absolute stroke budget exhausted');
 l.totalAbsoluteDegrees=next;l.status='reserved';l.entries.push({requestId:q.id,startB:q.expectedRaw.B,targetB:q.expectedRaw.B+q.deltaDegrees,deltaDegrees:q.deltaDegrees,absoluteDegrees:Math.abs(q.deltaDegrees),status:'reserved'});return l;
}
function finish(old,q,success){var l=JSON.parse(JSON.stringify(old)),e=l.entries[l.entries.length-1];if(l.status!=='reserved'||!e||e.requestId!==q.id)fail('Unknown reserved commissioning stroke');e.status=success?'verified':'faulted';l.status=e.status;if(success)l.lastVerifiedB=e.targetB;return l;}
var api={validate:validate,reserve:reserve,finish:finish,allowedSteps:steps.slice()};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.CommissioningStroke=api;
})(this);
