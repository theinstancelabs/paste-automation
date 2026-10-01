/* Pure policy/parser for one reviewed stationary B-current change. */
(function(root){'use strict';
function fail(s){throw Error(s);}function finite(v){return typeof v==='number'&&isFinite(v);}var hash=/^[a-f0-9]{64}$/;
function validate(q,now,jvm){
 if(!q||q.schema!==1||q.scope!=='stationary-native-B-current-adjustment'||q.enabled!==false)fail('Disabled reviewed B-current request required');
 if(typeof q.id!=='string'||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(q.id)||q.jvmStartMs!==jvm||!finite(q.createdMs)||q.createdMs>now||now-q.createdMs>300000)fail('Fresh exact JVM request required');
 if(typeof q.operator!=='string'||!q.operator.trim()||q.reviewedCurrentChange!==true)fail('Positive operator review required');
 if(!hash.test(q.liveConfigurationSha256)||!q.sourceBarrierEvidence||typeof q.sourceBarrierEvidence.path!=='string'||q.sourceBarrierEvidence.path.charAt(0)!=='/'||!hash.test(q.sourceBarrierEvidence.sha256))fail('Hash-bound full source position barrier required');
 if(!((q.expectedCurrentMa===200&&q.targetCurrentMa===400)||(q.expectedCurrentMa===400&&q.targetCurrentMa===200)))fail('Only reviewed 200-to-400 or 400-to-200 B-current adjustment allowed');
 ['expectedRaw','expectedDriver'].forEach(function(k){if(!q[k]||Object.keys(q[k]).sort().join(',')!=='A,B,X,Y,Z'||Object.keys(q[k]).some(function(a){return !finite(q[k][a]);}))fail('Exact finite five-axis '+k+' required');});
 if(!q.expectedNativePoses||Object.keys(q.expectedNativePoses).sort().join(',')!=='N1,N2,bottom,top')fail('Four exact native poses required');
 Object.keys(q.expectedNativePoses).forEach(function(k){var p=q.expectedNativePoses[k];if(!p||!finite(p.x)||!finite(p.y)||!finite(p.z)||!finite(p.rotation))fail('Finite complete native pose required');});
 return q;
}
function sourceBarrier(b,q){if(!b||b.status!=='completed-read-only-position-barrier'||b.controllerPositionVerified!==true||b.noMotionCommandSubmitted!==true||b.uncertainCompletion!==false||!b.request||b.request.jvmStartMs!==q.jvmStartMs||b.liveConfigurationSha256!==q.liveConfigurationSha256||b.request.liveConfigurationSha256!==q.liveConfigurationSha256)fail('Successful full same-session stationary barrier required');
 function same(a,z,keys,label){if(!a||!z)fail(label+' missing');keys.forEach(function(k){if(!finite(a[k])||a[k]!==z[k])fail(label+' mismatch '+k);});}
 same(b.afterQuerySnapshot.raw,q.expectedRaw,['X','Y','Z','A','B'],'Barrier raw pose');same(b.afterQuerySnapshot.driver,q.expectedDriver,['X','Y','Z','A','B'],'Barrier driver pose');
 Object.keys(q.expectedNativePoses).forEach(function(k){same(b.afterQuerySnapshot.nativePoses[k],q.expectedNativePoses[k],['x','y','z','rotation'],'Barrier '+k+' pose');});return true;}
function parseM906(lines){var values={},found=false,auxiliary=[];lines.forEach(function(line){var s=String(line),match=/\bM906\b/.exec(s);if(!match)return;found=true;var tokens=s.slice(match.index+4).trim().split(/\s+/);if(tokens.some(function(t){return /^I\d+$/.test(t);})){auxiliary.push(s.trim());return;}tokens.forEach(function(t){var m=/^([XYZAB])(\d+)$/.exec(t);if(!m)return;var k=m[1];if(Object.prototype.hasOwnProperty.call(values,k))fail('Duplicate M906 axis current '+k);values[k]=Number(m[2]);});});if(!found||Object.keys(values).sort().join(',')!=='A,B,X,Y,Z')fail('M503 must report one complete M906 X/Y/Z/A/B current line');values.auxiliary=auxiliary;return values;}
function verifyOnlyBChanged(before,after,expected,target){['X','Y','Z','A'].forEach(function(k){if(before[k]!==after[k])fail('M906 '+k+' current changed');});if(JSON.stringify(before.auxiliary||[])!==JSON.stringify(after.auxiliary||[]))fail('Indexed M906 current settings changed');if(before.B!==expected||after.B!==target)fail('M906 B current differs from reviewed before/target');return true;}
var api={validate:validate,sourceBarrier:sourceBarrier,parseM906:parseM906,verifyOnlyBChanged:verifyOnlyBChanged};if(typeof module!=='undefined')module.exports=api;else root.PasteBCurrent=api;
})(this);
