/* Pure contract: no controller or configuration API. */
(function(root){'use strict';
function validate(q,now,jvm){
 if(!q||q.schema!==1||q.scope!=='install-absent-native-error-latch-in-memory'||q.expectedPreviousCommand!==null)throw Error('Exact absent-latch installation contract required');
 if(typeof q.id!=='string'||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(q.id))throw Error('Fresh UUID required');
 if(typeof q.createdMs!=='number'||!isFinite(q.createdMs)||q.createdMs>now||now-q.createdMs>300000||q.jvmStartMs!==jvm)throw Error('Stale/different JVM');
 ['liveConfigurationSha256','diskMachineSha256'].forEach(function(k){if(typeof q[k]!=='string'||!/^[a-f0-9]{64}$/.test(q[k]))throw Error('Exact '+k+' required');});
 if(typeof q.operator!=='string'||!q.operator.trim()||q.reviewedNoMotionConfigurationChange!==true)throw Error('Reviewed operator required');
 if(Object.keys(q).some(function(k){return /command|regex/i.test(k)&&k!=='expectedPreviousCommand';}))throw Error('No caller-supplied command or regex allowed');
 return q;
}
var api={validate:validate};if(typeof module!=='undefined')module.exports=api;else root.PasteErrorLatchInstall=api;
})(this);
