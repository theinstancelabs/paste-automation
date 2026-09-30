/* Fresh fixed stationary camera LED restore request; no machine API. */
(function(root){'use strict';
function finite(v){return typeof v==='number'&&isFinite(v);}
function validate(q,now,jvm){
 if(!q||q.schema!==1||q.scope!=='stationary-native-camera-LED-restore')throw Error('Stationary LED request required');
 if(typeof q.id!=='string'||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(q.id))throw Error('Fresh UUID required');
 if(!finite(q.createdMs)||q.createdMs>now||now-q.createdMs>300000||q.jvmStartMs!==jvm)throw Error('Stale/different JVM');
 if(typeof q.operator!=='string'||!q.operator.trim()||q.reviewedStationaryLED!==true)throw Error('Reviewed operator required');
 if(typeof q.liveConfigurationSha256!=='string'||!/^[a-f0-9]{64}$/.test(q.liveConfigurationSha256))throw Error('Exact live configuration hash required');
 ['expectedRaw','expectedDriver'].forEach(function(k){if(!q[k]||Object.keys(q[k]).sort().join(',')!=='A,B,X,Y,Z'||Object.keys(q[k]).some(function(a){return !finite(q[k][a]);}))throw Error('Exact five-axis snapshot required');});
 if(!q.expectedNativePoses||Object.keys(q.expectedNativePoses).sort().join(',')!=='N1,N2,bottom,top')throw Error('Four exact native poses required');
 Object.keys(q.expectedNativePoses).forEach(function(k){var p=q.expectedNativePoses[k];if(!p||Object.keys(p).sort().join(',')!=='rotation,x,y,z'||Object.keys(p).some(function(a){return !finite(p[a]);}))throw Error('Finite complete native pose required');});
 if(Object.keys(q).some(function(k){return /command|regex|delta|target|axis|speed/i.test(k);}))throw Error('LED request cannot specify commands or motion');
 return q;
}
function commandContract(actuate,ack){
 if(String(actuate).trim()!=='{True:M150 P255 R255 U255 B255}{False:M150 P0}'||String(ack).trim()!=='^ok.*')throw Error('Fixed single LED boolean command/ACK changed');
}
var api={validate:validate,commandContract:commandContract};if(typeof module!=='undefined')module.exports=api;else root.PasteCameraLED=api;
})(this);
