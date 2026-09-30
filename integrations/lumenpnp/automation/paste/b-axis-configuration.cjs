/* Pure two-field B configuration request/XML contract; no machine API. */
(function(root){'use strict';
function finite(v){return typeof v==='number'&&isFinite(v);}
function validate(q,now,jvm){
 if(!q||q.schema!==1||q.scope!=='configure-native-B-prerequisites-in-memory')throw Error('Exact B prerequisite configuration request required');
 if(typeof q.id!=='string'||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(q.id))throw Error('Fresh UUID required');
 if(!finite(q.createdMs)||q.createdMs>now||now-q.createdMs>300000||q.jvmStartMs!==jvm)throw Error('Stale/different JVM');
 if(typeof q.operator!=='string'||!q.operator.trim()||q.reviewedNoMotionConfigurationChange!==true)throw Error('Reviewed operator required');
 if(typeof q.liveConfigurationSha256!=='string'||!/^[a-f0-9]{64}$/.test(q.liveConfigurationSha256))throw Error('Exact live configuration hash required');
 if(!q.barrierEvidence||typeof q.barrierEvidence.path!=='string'||q.barrierEvidence.path.charAt(0)!=='/'||!/^[a-f0-9]{64}$/.test(q.barrierEvidence.sha256))throw Error('Exact successful position barrier evidence required');
 ['expectedRaw','expectedDriver'].forEach(function(k){if(!q[k]||Object.keys(q[k]).sort().join(',')!=='A,B,X,Y,Z'||Object.keys(q[k]).some(function(a){return !finite(q[k][a]);}))throw Error('Exact five-axis snapshot required');});
 if(!q.expectedNativePoses||Object.keys(q.expectedNativePoses).sort().join(',')!=='N1,N2,bottom,top')throw Error('Four exact native poses required');
 Object.keys(q.expectedNativePoses).forEach(function(k){var p=q.expectedNativePoses[k];if(!p||Object.keys(p).sort().join(',')!=='rotation,x,y,z'||Object.keys(p).some(function(a){return !finite(p[a]);}))throw Error('Finite complete native pose required');});
 if(Object.keys(q).some(function(k){return /command|regex|delta|target|axis|speed/i.test(k);}))throw Error('Configuration request cannot specify commands or motion');
 if(typeof q.diskMachineSha256!=='string'||!/^[a-f0-9]{64}$/.test(q.diskMachineSha256))throw Error('Exact disk hash required');
 return q;
}
function expectedXml(before){
 var blocks=before.match(/<axis\b[^>]*\bid="AXS17108288e61da5fb"[^>]*>[\s\S]*?<\/axis>/g);
 if(!blocks||blocks.length!==1||! /\blimit-rotation="true"/.test(blocks[0]))throw Error('Exact single limited B axis required');
 var feeds=blocks[0].match(/<feedrate-per-second\b[^>]*\bvalue="50000\.0"[^>]*>/g);
 if(!feeds||feeds.length!==1)throw Error('Expected legacy B feedrate50000.0 required');
 var updated=blocks[0].replace('limit-rotation="true"','limit-rotation="false"').replace(feeds[0],feeds[0].replace('value="50000.0"','value="100.0"'));
 return before.replace(blocks[0],updated);
}
var api={validate:validate,expectedXml:expectedXml};if(typeof module!=='undefined')module.exports=api;else root.PasteBConfiguration=api;
})(this);
