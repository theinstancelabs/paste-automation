const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const z=require('./z-observation.cjs');
const raw=()=>({X:100,Y:200,Z:26.5,A:200,B:720});
function poses(){return {N1:{x:1,y:2,z:26.5,rotation:200},N2:{x:3,y:4,z:36.5,rotation:720},top:{x:5,y:6,z:0,rotation:0},bottom:{x:7,y:8,z:25.2,rotation:0}};}
function request(){const q=JSON.parse(fs.readFileSync(__dirname+'/z-observation.pending.json'));Object.assign(q,{id:'12345678-1234-1234-1234-123456789abc',createdMs:1000,jvmStartMs:1,operator:'synthetic',liveConfigurationSha256:'a'.repeat(64),deltaMm:1,nativeZConfiguration:{softLowEnabled:false,softLowMm:0,softHighEnabled:false,softHighMm:0,safeLowEnabled:true,safeLowMm:26.5,safeHighEnabled:true,safeHighMm:36.5},barrierEvidence:{path:'/synthetic-barrier.json',sha256:'c'.repeat(64)},operatorVerifiedJointZStep:true,bothHeadsClearAlongStep:true,motionAreaClear:true,noHeldPartsObserved:true,expectedRaw:raw(),expectedDriver:raw(),expectedNativePoses:poses(),corridorEvidence:{path:'/synthetic-only.png',sha256:'b'.repeat(64),capturedMs:900},jointInterval:{minRawZ:26.5,maxRawZ:27.5,reviewedForCurrentPose:true,reviewRecord:'synthetic-only'}});q.reviewedFirmwareZStepsPerMm=40;q.firmwareSettingsEvidence={path:'/synthetic-firmware.json',sha256:'d'.repeat(64),noInterveningResetOrSettingsChange:true,configurationLineageReview:'synthetic same-connection configuration lineage'};return q;}
test('pending cannot authorize and only discrete signed1/5mm Z observations are admitted',()=>{
 assert.throws(()=>z.validate(JSON.parse(fs.readFileSync(__dirname+'/z-observation.pending.json')),1001,1));z.validate(request(),1001,1);
 for(const delta of [-6,-2,-.5,0,1e-8,.025,.5,1.001,2,6,NaN,Infinity,'1']){const q=request();q.deltaMm=delta;assert.throws(()=>z.step(q));}
 for(const edit of [{axis:'X'},{axis:'B'},{axes:['Z']},{target:{Z:27.5}},{deltaZ:1}])assert.throws(()=>z.step({...request(),...edit}));
});
test('whole proposed step remains within explicit reviewed interval and full configured travel speed is required',()=>{
 for(const change of [q=>q.expectedRaw.Z=26.49,q=>q.expectedRaw.Z=35.51,q=>q.jointInterval.reviewedForCurrentPose=false,q=>q.jointInterval.maxRawZ=40,q=>q.speedFraction=.05,q=>q.speedFraction=.1,q=>q.speedOverPrecision=false]){const q=request();change(q);assert.throws(()=>z.validate(q,1001,1));}
 const q=request();q.expectedRaw.Z=35.5;q.jointInterval.minRawZ=35.5;q.jointInterval.maxRawZ=36.5;z.validate(q,1001,1);
});
test('fresh identity, all evidence, no-held-parts and complete exact start are required',()=>{
 for(const change of [q=>q.jvmStartMs=2,q=>q.createdMs=1002,q=>q.createdMs=-300000,q=>q.corridorEvidence.capturedMs=-300000,q=>q.corridorEvidence.capturedMs=1001,q=>q.operatorVerifiedJointZStep=false,q=>q.bothHeadsClearAlongStep=false,q=>q.noHeldPartsObserved=false,q=>delete q.expectedRaw.B,q=>q.expectedDriver.Z=NaN,q=>delete q.expectedNativePoses.N2]){const q=request();change(q);assert.throws(()=>z.validate(q,1001,1));}
});
test('target construction cannot change XYAB or wrap B720',()=>{
 const before=raw(),after=z.target(before,request());assert.deepEqual(after,{...before,Z:27.5});assert.deepEqual(before,raw());
 z.compareFirmwareStep(before,after,request());
 for(const k of ['X','Y','A','B']){const wrong={...after,[k]:after[k]+1};assert.throws(()=>z.compareFirmwareStep(before,wrong,request()));}
 assert.throws(()=>z.compareFirmwareStep(before,{...after,B:0},request()));
 assert.throws(()=>z.compareFirmwareStep(before,before,request()));
});
test('native relative polarity raises N1 lowers N2 and leaves cameraZ unchanged',()=>{
 const before=poses(),after=poses();after.N1.z+=1;after.N2.z-=1;z.compareNativeStep(before,after,request());
 for(const change of [p=>p.N2.z+=2,p=>p.N1.z-=2,p=>p.top.z+=1,p=>p.N2.rotation=0,p=>p.N1.x+=.03]){const wrong=JSON.parse(JSON.stringify(after));change(wrong);assert.throws(()=>z.compareNativeStep(before,wrong,request()));}
});
test('report precision tolerance does not relax exact request start or hide failed Z motion',()=>{
 const before=raw(),after={...before,Z:27.5,Y:200.001};z.compareFirmwareStep(before,after,request());z.comparePostModel(after,{...before,Z:27.5});
 assert.throws(()=>z.compareExact({...before,Y:200.001},before,'start'));
 assert.throws(()=>z.compareReported({...before,Z:27.5},before,before));
 assert.throws(()=>z.compareReported({...before,B:0},before,before));
});

test('activation binds fresh successful stationary barrier to exact same state',()=>{
 const q=request(),r={status:'completed-read-only-position-barrier',noMotionCommandSubmitted:true,controllerPositionVerified:true,uncertainCompletion:false,request:{jvmStartMs:1,liveConfigurationSha256:q.liveConfigurationSha256},liveConfigurationSha256:q.liveConfigurationSha256,finishedAt:new Date(950).toISOString(),afterQuerySnapshot:{raw:raw(),driver:raw(),nativePoses:poses()},reported:raw()};z.barrier(r,q,1001);
 for(const edit of [{status:'failed'},{controllerPositionVerified:false},{uncertainCompletion:true},{finishedAt:new Date(-300000).toISOString()},{liveConfigurationSha256:'d'.repeat(64)}])assert.throws(()=>z.barrier({...r,...edit},q,1001));
 const wrong=JSON.parse(JSON.stringify(r));wrong.afterQuerySnapshot.nativePoses.N2.z+=1;assert.throws(()=>z.barrier(wrong,q,1001));
 const rawWrong=JSON.parse(JSON.stringify(r));rawWrong.afterQuerySnapshot.raw.B=0;assert.throws(()=>z.barrier(rawWrong,q,1001));
});

test('physical review interval must equal only this explicit segment',()=>{const q=request();q.jointInterval.minRawZ=26.5;q.jointInterval.maxRawZ=27.5;z.validate(q,1001,1);q.jointInterval.maxRawZ=27.49;assert.throws(()=>z.validate(q,1001,1));q.jointInterval.maxRawZ=27.5;q.jointInterval.minRawZ=26.51;assert.throws(()=>z.validate(q,1001,1));});

test('all signed steps preserve XYAB and prove opposing native Z polarity',()=>{
 for(const delta of [-5,-1,1,5]){
  const q=request();q.deltaMm=delta;q.jointInterval.minRawZ=Math.min(26.5,26.5+delta);q.jointInterval.maxRawZ=Math.max(26.5,26.5+delta);z.validate(q,1001,1);
  const after=z.target(raw(),q);assert.deepEqual(after,{...raw(),Z:26.5+delta});z.compareFirmwareStep(raw(),after,q);
  const p=poses();p.N1.z+=delta;p.N2.z-=delta;z.compareNativeStep(poses(),p,q,.0001);
  p.N2.z+=delta*2;assert.throws(()=>z.compareNativeStep(poses(),p,q,.0001));
 }
});
test('safe zones and disabled soft limits are recorded but are not fabricated travel bounds',()=>{
 const q=request();q.deltaMm=-5;q.jointInterval.minRawZ=21.5;q.jointInterval.maxRawZ=26.5;z.validate(q,1001,1);
 q.nativeZConfiguration.softLowEnabled=true;q.nativeZConfiguration.softLowMm=21.51;assert.throws(()=>z.validate(q,1001,1));
 q.nativeZConfiguration.softLowMm=21.5;z.validate(q,1001,1);
 q.nativeZConfiguration.softHighEnabled=true;q.nativeZConfiguration.softHighMm=26.49;assert.throws(()=>z.validate(q,1001,1));
 q.nativeZConfiguration.softHighMm=26.5;z.validate(q,1001,1);
 for(const k of Object.keys(q.nativeZConfiguration)){
  const changed={...q.nativeZConfiguration,[k]:typeof q.nativeZConfiguration[k]==='boolean'?!q.nativeZConfiguration[k]:q.nativeZConfiguration[k]+.01};
  assert.throws(()=>z.nativeConfiguration(changed,q));
 }
 const malformed=request();malformed.nativeZConfiguration.safeLowEnabled=1;assert.throws(()=>z.validate(malformed,1001,1));
});


test('fine Z choices require request review and separate activation with unchanged evidence gates',()=>{
 for(const delta of [-.5,-.25,-.1,.1,.25,.5]){
  const q=request();q.deltaMm=delta;q.jointInterval.minRawZ=Math.min(26.5,26.5+delta);q.jointInterval.maxRawZ=Math.max(26.5,26.5+delta);
  assert.throws(()=>z.step(q));q.reviewedFineZStep=true;z.validate(q,1001,1);
  assert.throws(()=>z.fineStepGate(q,false));z.fineStepGate(q,true);
  const after=z.target(raw(),q);assert.deepEqual(after,{...raw(),Z:26.5+delta});z.compareFirmwareStep(raw(),after,q);
  const p=poses();p.N1.z+=delta;p.N2.z-=delta;z.compareNativeStep(poses(),p,q,.0001);
  q.jointInterval.maxRawZ+=.001;assert.throws(()=>z.validate(q,1001,1));
 }
 z.fineStepGate(request(),false);
 for(const delta of [.025,.05,.125,.2,.75])assert.throws(()=>z.step({...request(),deltaMm:delta,reviewedFineZStep:true}));
});
test('full M114 count delimiter requires exactly one complete integer XYZAB payload',()=>{
 const line='X:100.00 Y:200.00 Z:26.50 A:200.00 B:720.00 Count X:32000 Y:64000 Z:1060 A:888 B:3197';
 assert.deepEqual(z.controllerCounts([line,'ok']),{X:32000,Y:64000,Z:1060,A:888,B:3197});
 for(const lines of [[],['ok'],[line,line],[line,line.replace(' Z:1060',' Z:1060.5')],[line,'Count Z:1060'],[line.replace(' Z:1060',' Z:1060.5')],[line.replace(' B:3197','')],[line.replace(' Z:1060',' Z:9007199254740992')]])assert.throws(()=>z.controllerCounts(lines));
});
test('fine controller steps must be exact 4/10/20, with every other controller count unchanged',()=>{
 const before={X:32000,Y:64000,Z:1060,A:888,B:3197};
 for(const delta of [-.5,-.25,-.1,.1,.25,.5]){
  const q={...request(),deltaMm:delta,reviewedFineZStep:true},after={...before,Z:before.Z+Math.round(delta*40)};
  const result=z.compareControllerCounts(before,after,q);assert.equal(result.expectedSignedZSteps,delta*40);assert.equal(result.physicalDisplacementVerified,false);
  for(const axis of ['X','Y','Z','A','B'])assert.throws(()=>z.compareControllerCounts(before,{...after,[axis]:after[axis]+1},q));
 }
});
test('fine activation is explicitly enabled in runtime source behind policy evidence gates',()=>{
 const source=fs.readFileSync(__dirname+'/../scripts/Observe_Paste_Z.js','utf8');assert.match(source,/var PASTE_FINE_Z_OBSERVATION_ENABLED = true;/);
 assert.ok(source.indexOf('PasteZObservation.fineStepGate(q,PASTE_FINE_Z_OBSERVATION_ENABLED)')<source.indexOf('d.getReportedLocation('));
});

test('fine firmware calibration binds same-JVM acknowledged post-reset M503 and reviewed unchanged lineage',()=>{
 const q={...request(),deltaMm:.1,reviewedFineZStep:true},r={status:'connected-disabled-unhomed-reported-frame-synchronized',controllerFrameSynchronized:true,jvmStartMs:1,driverId:'DRV16982438146c1dd4',queries:[{command:'M503',status:'acknowledged',responses:['echo:  M92 X320.00 Y320.00 Z40.00 A4.44 B4.44','ok']}]};
 assert.equal(z.firmwareStepsEvidence(r,q).firmwareZStepsPerMm,40);
 for(const edit of [{jvmStartMs:2},{status:'failed'},{driverId:'other'},{controllerFrameSynchronized:false}])assert.throws(()=>z.firmwareStepsEvidence({...r,...edit},q));
 for(const line of ['echo:  M92 X320 Y320 Z80 A4.44 B4.44','echo: M92 Z40','echo: M92 X320 Y320 Z40 A4.44 B4.44\nM92 Z80']){const bad=JSON.parse(JSON.stringify(r));bad.queries[0].responses=[line,'ok'];assert.throws(()=>z.firmwareStepsEvidence(bad,q));}
 for(const edit of [{reviewedFirmwareZStepsPerMm:80},{firmwareSettingsEvidence:{...q.firmwareSettingsEvidence,noInterveningResetOrSettingsChange:false}},{firmwareSettingsEvidence:{...q.firmwareSettingsEvidence,sha256:'bad'}}])assert.throws(()=>z.step({...q,...edit}));
});

function measuredStepEvidence(){
 const fine={...request(),deltaMm:-.5,reviewedFineZStep:true,firmwareStepEvidence:{path:'/synthetic-measured-z-step.json',sha256:'e'.repeat(64)}};fine.jointInterval.minRawZ=26.0;fine.jointInterval.maxRawZ=26.5;
 const before={X:94688,Y:97664,Z:1900,A:3197,B:-1066},after={...before,Z:1700},braw={X:295.9,Y:305.2,Z:47.5,A:720,B:-240},araw={...braw,Z:42.5};
 const line=(p,c)=>`X:${p.X.toFixed(2)} Y:${p.Y.toFixed(2)} Z:${p.Z.toFixed(2)} A:${p.A.toFixed(2)} B:${p.B.toFixed(2)} Count X:${c.X} Y:${c.Y} Z:${c.Z} A:${c.A} B:${c.B}`;
 const sourceRequest={schema:2,scope:'bounded-signed-raw-Z-observation',id:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',jvmStartMs:1,liveConfigurationSha256:fine.liveConfigurationSha256,axis:'Z',deltaMm:-5,expectedRaw:braw,expectedDriver:braw};
 const record={id:sourceRequest.id,status:'completed-Z-observation-awaiting-image-review',request:sourceRequest,finishedAt:new Date(900).toISOString(),uncertainCompletion:false,motionSubmitted:true,nativeMotionCompletionReported:true,controllerPositionVerified:true,independentFirmwareStepVerified:true,commandedControllerAxes:['Z'],before:{saved:{raw:braw,driver:braw},reported:braw,responses:[line(braw,before),'ok']},after:{saved:{raw:araw,driver:araw},reported:araw,responses:[line(araw,after),'ok']},afterQuerySnapshot:{raw:araw,driver:araw}};
 return {fine,record,before,after};
}
test('fine step scale can use hashed same-JVM completed Z-count evidence without reconnect evidence',()=>{
 const {fine,record}=measuredStepEvidence();assert.equal(z.firmwareStepsEvidence(record,fine,1001).firmwareZStepsPerMm,40);z.validate(fine,1001,1);
 for(const edit of [{uncertainCompletion:true},{controllerPositionVerified:false},{independentFirmwareStepVerified:false},{commandedControllerAxes:['Z','B']},{request:{...record.request,jvmStartMs:2}},{request:{...record.request,liveConfigurationSha256:'f'.repeat(64)}},{afterControllerCounts:{X:1,Y:2,Z:3,A:4,B:5}}])assert.throws(()=>z.firmwareStepsEvidence({...record,...edit},fine,1001));
 for(const axis of ['X','Y','A','B']){const bad=JSON.parse(JSON.stringify(record)),index=['X','Y','Z','A','B'].indexOf(axis);bad.after.responses[0]=bad.after.responses[0].replace(/Count X:(-?\d+) Y:(-?\d+) Z:(-?\d+) A:(-?\d+) B:(-?\d+)/,(_,...values)=>'Count '+values.slice(0,5).map((v,i)=>Number(v)+(i===index?1:0)).map((v,i)=>['X','Y','Z','A','B'][i]+':'+v).join(' '));assert.throws(()=>z.firmwareStepsEvidence(bad,fine,1001));}
 const wrongZ=JSON.parse(JSON.stringify(record));wrongZ.after.responses[0]=wrongZ.after.responses[0].replace(' Z:1700',' Z:1701');assert.throws(()=>z.firmwareStepsEvidence(wrongZ,fine,1001));
 const wrongReported=JSON.parse(JSON.stringify(record));wrongReported.after.responses[0]=wrongReported.after.responses[0].replace('Z:42.50','Z:42.00');assert.throws(()=>z.firmwareStepsEvidence(wrongReported,fine,1001));
 for(const edit of [{sha256:'bad'},{path:'relative.json'}])assert.throws(()=>z.step({...fine,firmwareStepEvidence:edit}));
});
