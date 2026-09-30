const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const z=require('./z-observation.cjs');
const raw=()=>({X:100,Y:200,Z:26.5,A:200,B:720});
function poses(){return {N1:{x:1,y:2,z:26.5,rotation:200},N2:{x:3,y:4,z:36.5,rotation:720},top:{x:5,y:6,z:0,rotation:0},bottom:{x:7,y:8,z:25.2,rotation:0}};}
function request(){const q=JSON.parse(fs.readFileSync(__dirname+'/z-observation.pending.json'));Object.assign(q,{id:'12345678-1234-1234-1234-123456789abc',createdMs:1000,jvmStartMs:1,operator:'synthetic',liveConfigurationSha256:'a'.repeat(64),deltaMm:1,barrierEvidence:{path:'/synthetic-barrier.json',sha256:'c'.repeat(64)},operatorVerifiedJointZStep:true,bothHeadsClearAlongStep:true,motionAreaClear:true,noHeldPartsObserved:true,expectedRaw:raw(),expectedDriver:raw(),expectedNativePoses:poses(),corridorEvidence:{path:'/synthetic-only.png',sha256:'b'.repeat(64),capturedMs:900},jointInterval:{minRawZ:26.5,maxRawZ:36.5,reviewedForCurrentPose:true,reviewRecord:'synthetic-only'}});return q;}
test('pending cannot authorize and only exact positive1mm Z observation is admitted',()=>{
 assert.throws(()=>z.validate(JSON.parse(fs.readFileSync(__dirname+'/z-observation.pending.json')),1001,1));z.validate(request(),1001,1);
 for(const delta of [-1,0,1e-8,.025,.5,1.001,NaN,Infinity,'1']){const q=request();q.deltaMm=delta;assert.throws(()=>z.step(q));}
 for(const edit of [{axis:'X'},{axis:'B'},{axes:['Z']},{target:{Z:27.5}},{deltaZ:1}])assert.throws(()=>z.step({...request(),...edit}));
});
test('whole proposed step remains within explicit reviewed interval and speed cannot be silently clamped',()=>{
 for(const change of [q=>q.expectedRaw.Z=26.49,q=>q.expectedRaw.Z=35.51,q=>q.jointInterval.reviewedForCurrentPose=false,q=>q.jointInterval.maxRawZ=40,q=>q.speedFraction=.01,q=>q.speedFraction=.1,q=>q.speedOverPrecision=false]){const q=request();change(q);assert.throws(()=>z.validate(q,1001,1));}
 const q=request();q.expectedRaw.Z=35.5;z.validate(q,1001,1);
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

test('physical review interval may be narrower than application envelope',()=>{const q=request();q.jointInterval.minRawZ=26.5;q.jointInterval.maxRawZ=27.5;z.validate(q,1001,1);q.jointInterval.maxRawZ=27.49;assert.throws(()=>z.validate(q,1001,1));q.jointInterval.maxRawZ=27.5;q.jointInterval.minRawZ=26.51;assert.throws(()=>z.validate(q,1001,1));});
