/* Fresh read-only position request; no machine API. */
(function(root){'use strict';
function finite(v){return typeof v==='number'&&isFinite(v);}
function validate(q,now,jvm){
 if(!q||q.schema!==1||q.scope!=='read-only-native-position-barrier')throw Error('Position-only request required');
 if(typeof q.id!=='string'||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(q.id))throw Error('Fresh UUID required');
 if(!finite(q.createdMs)||q.createdMs>now||now-q.createdMs>300000||q.jvmStartMs!==jvm)throw Error('Stale/different JVM');
 if(typeof q.operator!=='string'||!q.operator.trim()||q.reviewedReadOnlyQuery!==true)throw Error('Reviewed operator required');
 if(typeof q.liveConfigurationSha256!=='string'||!/^[a-f0-9]{64}$/.test(q.liveConfigurationSha256))throw Error('Exact live configuration hash required');
 if(!q.installerEvidence||typeof q.installerEvidence.path!=='string'||q.installerEvidence.path.charAt(0)!=='/'||!/^[a-f0-9]{64}$/.test(q.installerEvidence.sha256))throw Error('Exact successful installer evidence required');
 ['expectedRaw','expectedDriver'].forEach(function(k){if(!q[k]||Object.keys(q[k]).sort().join(',')!=='A,B,X,Y,Z'||Object.keys(q[k]).some(function(a){return !finite(q[k][a]);}))throw Error('Exact five-axis snapshot required');});
 if(!q.expectedNativePoses||Object.keys(q.expectedNativePoses).sort().join(',')!=='N1,N2,bottom,top')throw Error('Four exact native poses required');
 Object.keys(q.expectedNativePoses).forEach(function(k){var p=q.expectedNativePoses[k];if(!p||Object.keys(p).sort().join(',')!=='rotation,x,y,z'||Object.keys(p).some(function(a){return !finite(p[a]);}))throw Error('Finite complete native pose required');});
 if(Object.keys(q).some(function(k){return /command|regex|delta|target|axis|speed/i.test(k);}))throw Error('Position request cannot specify commands or motion');
 return q;
}
function installer(record,q){
 var errorInstall=record&&record.status==='installed-in-memory-awaiting-read-only-barrier-and-review'&&record.previousCommand===null;
 var bConfig=record&&record.status==='configured-B-prerequisites-in-memory-awaiting-fresh-barrier'&&record.exactTwoFieldChangeVerified===true&&record.previousLimitRotation===true&&record.requestedLimitRotation===false&&record.previousFeedratePerSecond===50000&&record.requestedFeedratePerSecond===100&&record.extrusionAuthorized===false;
 if(!record||(!errorInstall&&!bConfig)||record.diskUnchanged!==true||record.coordinatesUnchanged!==true||record.noControllerCommands!==true||record.configurationSaved!==false||!record.request||record.request.jvmStartMs!==q.jvmStartMs||record.liveConfigurationAfterSha256!==q.liveConfigurationSha256)throw Error('Successful same-JVM configuration installer required');
}
var api={validate:validate,installer:installer};if(typeof module!=='undefined')module.exports=api;else root.PastePositionBarrier=api;
})(this);
