/* Fresh read-only position request; no machine API. */
(function(root){'use strict';
function finite(v){return typeof v==='number'&&isFinite(v);}
function validate(q,now,jvm){
 if(!q||q.schema!==1||q.scope!=='read-only-native-position-barrier')throw Error('Position-only request required');
 if(typeof q.id!=='string'||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(q.id))throw Error('Fresh UUID required');
 if(!finite(q.createdMs)||q.createdMs>now||now-q.createdMs>300000||q.jvmStartMs!==jvm)throw Error('Stale/different JVM');
 if(typeof q.operator!=='string'||!q.operator.trim()||q.reviewedReadOnlyQuery!==true)throw Error('Reviewed operator required');
 if(q.manualHomeAcknowledgement!==true)throw Error('Explicit operator acknowledgement of completed manual home required');
 if(typeof q.liveConfigurationSha256!=='string'||!/^[a-f0-9]{64}$/.test(q.liveConfigurationSha256))throw Error('Exact live configuration hash required');
 if(!q.installerEvidence||typeof q.installerEvidence.path!=='string'||q.installerEvidence.path.charAt(0)!=='/'||!/^[a-f0-9]{64}$/.test(q.installerEvidence.sha256))throw Error('Exact successful installer evidence required');
 ['expectedRaw','expectedDriver'].forEach(function(k){if(!q[k]||Object.keys(q[k]).sort().join(',')!=='A,B,X,Y,Z'||Object.keys(q[k]).some(function(a){return !finite(q[k][a]);}))throw Error('Exact five-axis snapshot required');});
 if(!q.expectedNativePoses||Object.keys(q.expectedNativePoses).sort().join(',')!=='N1,N2,bottom,top')throw Error('Four exact native poses required');
 Object.keys(q.expectedNativePoses).forEach(function(k){var p=q.expectedNativePoses[k];if(!p||Object.keys(p).sort().join(',')!=='rotation,x,y,z'||Object.keys(p).some(function(a){return !finite(p[a]);}))throw Error('Finite complete native pose required');});
 if(Object.keys(q).some(function(k){return /command|regex|delta|target|axis|speed/i.test(k);}))throw Error('Position request cannot specify commands or motion');
 return q;
}
function installer(record,q){
 if(record&&record.scope==='pure-model-state-no-controller-access'){
  var driver=record.drivers&&record.drivers.length===1?record.drivers[0]:null;
  var n2=record.nozzles&&record.nozzles.filter(function(n){return n.name==='N2';})[0];
  if(record.jvmStartMs!==q.jvmStartMs||record.liveConfigurationSha256!==q.liveConfigurationSha256||record.enabled!==true||record.homed!==true||record.busy!==false||record.controllerPoseTrusted!==false||record.motionQueue!==0||record.preRotate!==false||!record.executor||record.executor.shutdown!==false||record.executor.terminated!==false||record.executor.active!==0||record.executor.queued!==0||!driver||driver.connected!==true||driver.readerAlive!==true||driver.error!==null||driver.motionPending!==false||!n2||!n2.manualNozzleTipChangeLocation||n2.manualNozzleTipChangeLocation.initialized!==false||n2.tip!==null||n2.compatible!==0||n2.changer!==false||n2.part!==null)throw Error('Verified same-JVM idle homed model snapshot with N2 quarantine required');
  if(record.taskOwner&&record.taskOwner.alive===true)throw Error('Model snapshot has active task owner');
  return;
 }
 if(record&&record.status==='completed-native-home-enabled-awaiting-image-review'){
  if(!record.request||record.request.jvmStartMs!==q.jvmStartMs||record.liveConfigurationSha256!==q.liveConfigurationSha256||record.request.liveConfigurationSha256!==q.liveConfigurationSha256||record.controllerPositionVerified!==true||record.rotationUnchangedVerified!==true||record.nativeMotionCompletionReported!==true||record.uncertainCompletion!==false||record.diskUnchanged!==true||record.machineEnabled!==true||record.machineHomed!==true)throw Error('Verified same-JVM home configuration required');return;
 }

 var errorInstall=record&&record.status==='installed-in-memory-awaiting-read-only-barrier-and-review'&&record.previousCommand===null;
 var bConfig=record&&record.status==='configured-B-prerequisites-in-memory-awaiting-fresh-barrier'&&record.exactTwoFieldChangeVerified===true&&record.previousLimitRotation===true&&record.requestedLimitRotation===false&&record.previousFeedratePerSecond===50000&&record.requestedFeedratePerSecond===100&&record.extrusionAuthorized===false;
 if(!record||(!errorInstall&&!bConfig)||record.diskUnchanged!==true||record.coordinatesUnchanged!==true||record.noControllerCommands!==true||record.configurationSaved!==false||!record.request||record.request.jvmStartMs!==q.jvmStartMs||record.liveConfigurationAfterSha256!==q.liveConfigurationSha256)throw Error('Successful same-JVM configuration installer required');
}
function calibrationXml(before,after){
 var re=/(<entry>\s*<string>N1<\/string>\s*)(<runout-compensation\s[^>]*\/>)/g;
 function normalized(xml){var count=0;var out=xml.replace(re,function(all,prefix,tag){count++;var attrs={},m,ar=/([\w-]+)="([^"]*)"/g;while((m=ar.exec(tag))!==null)attrs[m[1]]=m[2];if(Object.keys(attrs).sort().join(',')!=='center-x,center-y,class,peak-error,phase-shift,radius,rms-error,units'||attrs['class']!=='org.openpnp.machine.reference.ReferenceNozzleTipCalibration$ModelBasedRunoutCameraOffsetCompensation'||attrs.units!=='Millimeters')throw Error('Unexpected N1 calibration type');['center-x','center-y','peak-error','phase-shift','radius','rms-error'].forEach(function(k){if(attrs[k].trim()===''||!isFinite(Number(attrs[k])))throw Error('Nonfinite N1 calibration');});return prefix+'<reviewed-N1-runout/>';});if(count!==1)throw Error('Exactly one N1 runout required');return out;}
 if(normalized(before)!==normalized(after))throw Error('Configuration changes beyond N1 runout calibration');return true;
}
var api={validate:validate,installer:installer,calibrationXml:calibrationXml};if(typeof module!=='undefined')module.exports=api;else root.PastePositionBarrier=api;
})(this);
