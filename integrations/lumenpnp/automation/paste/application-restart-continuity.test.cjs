'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const Policy=require('./application-restart-continuity.cjs');
const hash=v=>crypto.createHash('sha256').update(JSON.stringify(v)).digest('hex');
const oldRaw={X:359.78,Y:129.85,Z:32.25,A:720,B:-3266},newRaw={X:0,Y:0,Z:31.5,A:720,B:-3266};
const oldCounts={X:115130,Y:41552,Z:1290,A:3197,B:-14501},newCounts={X:0,Y:0,Z:1260,A:3197,B:-14501};
const sessionId='27c1ab29-a268-47d7-8dcf-eaf2a71ade02',oldJvmStartMs=1000,newJvmStartMs=2000,config='a'.repeat(64);
const m114=(raw,c)=>`X:${raw.X.toFixed(2)} Y:${raw.Y.toFixed(2)} Z:${raw.Z.toFixed(2)} A:${raw.A.toFixed(2)} B:${raw.B.toFixed(2)} Count X:${c.X} Y:${c.Y} Z:${c.Z} A:${c.A} B:${c.B}`;
function fixture(){
 const files={},ref=(path,value)=>{files[path]=value;return {path,sha256:hash(value)};};
 const old={schema:1,id:'old-air',status:'failed-no-retry-no-recovery-motion',finishedAt:new Date(3000).toISOString(),motionSubmitted:false,controllerQuerySubmitted:true,uncertainCompletion:false,request:{id:'old-air',sessionId,jvmStartMs:oldJvmStartMs,liveConfigurationSha256:config,mode:'air',expectedRaw:oldRaw},before:{reported:oldRaw,responses:[m114(oldRaw,oldCounts),'ok']}};
 const oldRef=ref('/evidence/old-air/report.json',old);
 const startup={scope:'pure-model-state-no-controller-access',time:new Date(4000).toISOString(),jvmStartMs:newJvmStartMs,enabled:true,homed:false,busy:false,liveConfigurationSha256:config,axes:Object.keys(oldRaw).map(letter=>({letter,raw:oldRaw[letter],driver:oldRaw[letter]}))};
 const startupRef=ref('/evidence/startup/report.json',startup);
 const home={id:'new-home',status:'completed-native-home-enabled-awaiting-image-review',startedAt:new Date(5000).toISOString(),finishedAt:new Date(6000).toISOString(),liveConfigurationSha256:config,controllerPositionVerified:true,uncertainCompletion:false,nativeMotionCompletionReported:true,rotationUnchangedVerified:true,diskUnchanged:true,request:{id:'new-home',sessionId,jvmStartMs:newJvmStartMs,liveConfigurationSha256:config,mode:'fresh-startup-home',homeReason:'user-requested-home-after-application-restart',sourceEvidence:startupRef},beforeQuerySnapshot:{raw:oldRaw,driver:oldRaw},before:{reported:oldRaw,responses:[m114(oldRaw,oldCounts),'ok']},after:{reported:newRaw,responses:[m114(newRaw,newCounts),'ok']},afterQuerySnapshot:{raw:newRaw,driver:newRaw}};
 const homeRef=ref('/evidence/home/report.json',home);
 const barrier={id:'new-barrier',status:'completed-read-only-position-barrier',finishedAt:new Date(7000).toISOString(),liveConfigurationSha256:config,controllerPositionVerified:true,uncertainCompletion:false,noMotionCommandSubmitted:true,request:{id:'new-barrier',scope:'read-only-native-position-barrier',jvmStartMs:newJvmStartMs,liveConfigurationSha256:config,installerEvidence:homeRef},position:{reported:newRaw,responses:[m114(newRaw,newCounts),'ok']},afterQuerySnapshot:{raw:newRaw,driver:newRaw}};
 const barrierRef=ref('/evidence/barrier/report.json',barrier);
 const record={schema:1,scope:'same-session-application-restart-continuity',sessionId,liveConfigurationSha256:config,reviewedBy:'reviewer',reviewBasis:'Reviewed the same-syringe, no-reset and no-manual-B-displacement continuity basis.',reviewedMs:8000,noControllerPowerCycleOrManualBDisplacement:true,transitions:[{oldJvmStartMs,newJvmStartMs,oldPositionEvidence:oldRef,startupModelEvidence:startupRef,homeEvidence:homeRef,postHomeBarrierEvidence:barrierRef}]};
 const appRef={path:'/evidence/restart-continuity.json',sha256:hash(record),sessionId,newJvmStartMs,liveConfigurationSha256:config,allowedJvmStartMs:[oldJvmStartMs,newJvmStartMs]};
 const q={sessionId,jvmStartMs:newJvmStartMs,liveConfigurationSha256:config,createdMs:9000,applicationRestartEvidence:appRef};
 const reader=e=>{const v=files[e.path];assert.ok(v);assert.equal(hash(v),e.sha256);return v;};
 return {files,record,q,reader,old,home,barrier};
}
test('authorizes only hash-bound same-session restart with matching M114 rotary coordinates/counts',()=>{const f=fixture();assert.deepEqual(Policy.validate(f.record,f.q,f.reader,10000),{sessionId,oldJvmStartMs,newJvmStartMs,allowedJvmStartMs:[oldJvmStartMs,newJvmStartMs],liveConfigurationSha256:config});});
test('rejects mismatched old, pre-home or post-home rotary position/counts',()=>{for(const change of [
 f=>{f.old.before.responses[0]=m114(oldRaw,{...oldCounts,B:-14500});},
 f=>{f.home.before.responses[0]=m114(oldRaw,{...oldCounts,A:3198});},
 f=>{f.home.after.responses[0]=m114({...newRaw,B:-3265},{...newCounts,B:-14500});},
 f=>{f.barrier.position.responses[0]=m114(newRaw,{...newCounts,B:-14500});},
]){const f=fixture();change(f);assert.throws(()=>Policy.validate(f.record,f.q,f.reader,10000));}});
test('rejects wrong session, configuration, home reason, power-cycle claim, or JVM mapping',()=>{const mutations=[
 f=>f.record.sessionId='other-session',f=>f.record.liveConfigurationSha256='f'.repeat(64),
 f=>f.home.request.homeReason='user-requested-home-after-power-cycle',
 f=>f.record.noControllerPowerCycleOrManualBDisplacement=false,
 f=>f.record.transitions[0].newJvmStartMs=oldJvmStartMs,
 f=>f.q.jvmStartMs=oldJvmStartMs,
 f=>f.q.applicationRestartEvidence.allowedJvmStartMs=[newJvmStartMs],
];for(const mutate of mutations){const f=fixture();mutate(f);assert.throws(()=>Policy.validate(f.record,f.q,f.reader,10000));}});
