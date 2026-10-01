/* Restricted post-reset homing request; no hardware calls. */
(function(root){'use strict';
function deliberate(q){return q.mode==='enabled-homed-rehome'&&q.homeReason==='user-requested-rehome-after-cleaning';}
function freshStartup(q){return q.mode==='fresh-startup-home'&&['user-requested-home-after-power-cycle','user-requested-home-after-application-restart'].indexOf(q.homeReason)>=0;}
function validate(q,now,jvm,Z){if(!q||q.schema!==1||q.scope!=='reviewed-post-reset-native-home'||q.jvmStartMs!==jvm||typeof q.createdMs!=='number'||!isFinite(q.createdMs)||q.createdMs>now||now-q.createdMs>300000||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(q.id))throw Error('Fresh homing request required');if(typeof q.operator!=='string'||!q.operator.trim()||q.reviewedEntireHomingEnvelope!==true||q.bothHeadsClearForXYAndZHome!==true||q.noHeldPartsObserved!==true||q.reviewedFirmwareNoABHoming!==true||q.enableAfterVerifiedHome!==true)throw Error('Explicit full homing/callback review required');if(!/^[a-f0-9]{64}$/.test(q.liveConfigurationSha256))throw Error('Exact configuration required');['sourceEvidence','corridorEvidence'].forEach(function(k){var e=q[k];if(!e||typeof e.path!=='string'||e.path.charAt(0)!=='/'||!/^[a-f0-9]{64}$/.test(e.sha256))throw Error('Hashed '+k+' required');});var t=q.corridorEvidence.capturedMs;if(typeof t!=='number'||!isFinite(t)||t>q.createdMs||now-t>300000)throw Error('Fresh full-home clearance image required');['expectedRaw','expectedDriver'].forEach(function(k){if(!q[k]||Object.keys(q[k]).sort().join(',')!=='A,B,X,Y,Z')throw Error('Five-axis start required');Z.compareExact(q[k],q[k],k);});if(q.mode!==undefined&&q.mode!=='post-reset'&&!deliberate(q)&&!freshStartup(q))throw Error('Explicit deliberate rehome mode/reason required');if(!deliberate(q)&&!freshStartup(q)&&(q.expectedRaw.A!==720||q.expectedRaw.B!==720))throw Error('Reviewed reset rotary frame required');['N1','N2','top','bottom'].forEach(function(k){['x','y','z','rotation'].forEach(function(a){Z.close(q.expectedNativePoses[k][a],q.expectedNativePoses[k][a],0,'finite native pose');});});return q;}
function source(s,q,now,Z){
 if(freshStartup(q)){
  if(!s||s.scope!=='pure-model-state-no-controller-access'||s.jvmStartMs!==q.jvmStartMs||s.enabled!==true||s.homed!==false||s.busy!==false||s.taskOwner!==null||s.motionQueue!==0||s.preRotate!==false||!s.executor||s.executor.shutdown!==false||s.executor.terminated!==false||s.executor.active!==0||s.executor.queued!==0)throw Error('Fresh same-JVM idle unhomed startup snapshot required');
  var d=s.drivers&&s.drivers.length===1?s.drivers[0]:null;if(!d||d.id!=='DRV16982438146c1dd4'||d.connected!==true||d.readerAlive!==true||d.error!==null||d.motionPending!==false)throw Error('Connected native driver/reader required');
  var t=Date.parse(s.time);if(!isFinite(t)||t>q.createdMs||now-t>300000||s.liveConfigurationSha256!==q.liveConfigurationSha256)throw Error('Fresh startup source/configuration required');
  var raw={},driver={};(s.axes||[]).forEach(function(a){if(!/^[XYZAB]$/.test(a.letter)||raw[a.letter]!==undefined)throw Error('Unexpected startup axis');raw[a.letter]=a.raw;driver[a.letter]=a.driver;});
  Z.compareExact(raw,q.expectedRaw,'startup raw');Z.compareExact(driver,q.expectedDriver,'startup driver');
  ['N1','N2','top','bottom'].forEach(function(k){['x','y','z','rotation'].forEach(function(a){Z.close(s.nativePoses[k][a],q.expectedNativePoses[k][a],.0001,'startup native');});});
  return;
 }
 var completedPrime=deliberate(q)&&s&&s.status==='completed-waste-prime-awaiting-observation';
 var completedHome=deliberate(q)&&s&&s.status==='completed-native-home-enabled-awaiting-image-review';
 if(deliberate(q)&&!completedPrime&&!completedHome)throw Error('Deliberate enabled rehome requires completed prime source');
 var clearance=s&&s.status==='completed-unhomed-positive-Z-clearance-awaiting-image-review';
 var finalized=s&&s.status==='completed-home-cache-finalization-disabled-unhomed';
 if(!completedPrime&&!completedHome&&!clearance&&!finalized)throw Error('Verified unhomed clearance or exact home-cache finalization required');
 if(s.controllerPositionVerified!==true||s.uncertainCompletion!==false||(!completedPrime&&!completedHome&&s.machineRemainsDisabledUnhomed!==true)||((completedPrime||completedHome)?s.request&&s.request.liveConfigurationSha256:s.liveConfigurationSha256)!==q.liveConfigurationSha256)throw Error('Verified same-session unhomed source required');
 if(completedPrime){if(s.countsVerified!==true||!s.request||s.request.jvmStartMs!==q.jvmStartMs)throw Error('Same-session verified completed prime required for deliberate rehome');}
 else if(completedHome){if(!s.request||s.request.jvmStartMs!==q.jvmStartMs||s.rotationUnchangedVerified!==true||s.nativeMotionCompletionReported!==true||s.machineEnabled!==true||s.machineHomed!==true||s.diskUnchanged!==true)throw Error('Verified same-session completed home required');}
 else if(clearance){if(s.independentFirmwareStepVerified!==true||!s.request||s.request.jvmStartMs!==q.jvmStartMs)throw Error('Verified same-session unhomed clearance required');}
 else{
  // This source proves only firmware/model cache identity. Prolonged idle can
  // release steppers, so a newly reviewed physical envelope and deliberate new
  // home are required; the old completed G28 never establishes current trust.
  if(s.scope!=='exact-home-audit-finalization-no-motion'||s.jvmStartMs!==q.jvmStartMs||s.noHome!==true||s.noMotion!==true||s.noEnable!==true||s.machineEnabled!==false||s.machineHomed!==false||s.absolutePhysicalPositionUnknown!==true||s.physicalRegistrationInvalidated!==true||s.rotationUnchangedVerified!==true||s.diskUnchanged!==true||q.homeReason!=='deliberate-rehome-after-prolonged-idle')throw Error('Explicit newly reviewed home after idle required');
 }
 var t=Date.parse(s.finishedAt);if(!isFinite(t)||t>q.createdMs||now-t>1800000)throw Error('Unhomed source stale');
 Z.compareExact(s.afterQuerySnapshot.raw,q.expectedRaw,'source raw');Z.compareExact(s.afterQuerySnapshot.driver,q.expectedDriver,'source driver');
 ['N1','N2','top','bottom'].forEach(function(k){['x','y','z','rotation'].forEach(function(a){Z.close(s.afterQuerySnapshot.nativePoses[k][a],q.expectedNativePoses[k][a],.0001,'source native');});});
}
function reported(r,before,Z){if(!r||Object.keys(r).sort().join(',')!=='A,B,X,Y,Z')throw Error('Full fresh home report required');['X','Y'].forEach(function(k){Z.close(r[k],0,.02,'firmware safe-home '+k);});Z.close(r.Z,31.5,.02,'firmware posthome Z');['A','B'].forEach(function(k){Z.close(r[k],before[k],.3,'unchanged home rotary '+k);});}
function position(line){var match=String(line).match(/^.*X:(-?\d+\.\d+)\s*Y:(-?\d+\.\d+)\s*Z:(-?\d+\.\d+)\s*A:(-?\d+\.\d+)\s*B:(-?\d+\.\d+).*/);if(!match){if(/\b[XYZAB]:/.test(String(line)))throw Error('Malformed position report');return null;}var r={};['X','Y','Z','A','B'].forEach(function(k,i){r[k]=Number(match[i+1]);});return r;}
// G28 may emit one ordinary position report before its ACK. It is audited as
// prior evidence, never used as the subsequently requested M114 response.
function priorHomeResponses(lines,before,Z){var count=0;lines.forEach(function(line){var p=position(line);if(p){reported(p,before,Z);count++;}});if(count>1)throw Error('Multiple prior home position reports');return count;}
function freshHomeResponses(lines,observed,before,Z){var positions=[],delimiter=-1;lines.forEach(function(line,i){var p=position(line);if(p){positions.push(p);delimiter=i;}});if(positions.length!==1)throw Error('Exactly one fresh M114 position required');if(!lines.slice(delimiter+1).some(function(line){return /^ok/.test(String(line));}))throw Error('Following fresh M114 ACK required');reported(positions[0],before,Z);reported(observed,before,Z);Z.compareExact(positions[0],observed,'full M114 response matches native report');return positions[0];}
var api={deliberate:deliberate,freshStartup:freshStartup,validate:validate,source:source,reported:reported,priorHomeResponses:priorHomeResponses,freshHomeResponses:freshHomeResponses};if(typeof module!=='undefined')module.exports=api;else root.PasteResetHome=api;
})(this);
