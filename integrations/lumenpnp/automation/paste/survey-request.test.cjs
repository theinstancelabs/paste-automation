const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const p=require('./survey-request.cjs');
function request(){const pose={x:1,y:2,z:3,rotation:4};return {schema:1,scope:'camera-survey-raw-X-plus10-only',id:'12345678-1234-1234-1234-123456789abc',createdMs:1000,jvmStartMs:42,operator:'synthetic test',liveConfigurationSha256:'a'.repeat(64),deltaRawXmm:10,speedFraction:0.1,speedOverPrecision:true,operatorVerified10mmCorridor:true,bothHeadsClearAlongCorridor:true,motionAreaClear:true,noHeldPartsObserved:true,corridorEvidence:{path:'/synthetic/corridor.png',sha256:'b'.repeat(64),capturedMs:900},expectedRaw:{X:20,Y:30,Z:40,A:50,B:720},expectedDriver:{X:20,Y:30,Z:40,A:50,B:720},expectedNativePoses:{N1:{...pose},N2:{...pose},top:{...pose},bottom:{...pose}}};}
test('pending survey request cannot authorize motion',()=>assert.throws(()=>p.validate(JSON.parse(fs.readFileSync(__dirname+'/survey-request.pending.json')),1001,42)));
test('only exact10mm survey scope with approved conservative speed',()=>{p.validate(request(),1001,42);for(const [key,value] of [['deltaRawXmm',-10],['deltaRawXmm',11],['speedFraction',0.2],['scope','air-run'],['speedOverPrecision',false]]){const q=request();q[key]=value;assert.throws(()=>p.validate(q,1001,42));}});
test('JVM and short-lived current request are bound',()=>{assert.throws(()=>p.validate(request(),301001,42));assert.throws(()=>p.validate(request(),999,42));assert.throws(()=>p.validate(request(),1001,43));});
test('physical corridor/evidence and all poses mandatory',()=>{for(const alter of [q=>q.bothHeadsClearAlongCorridor=false,q=>q.corridorEvidence.sha256=null,q=>q.corridorEvidence.capturedMs=-300000,q=>q.expectedRaw.Z=null,q=>delete q.expectedNativePoses.N2]){const q=request();alter(q);assert.throws(()=>p.validate(q,1001,42));}});
test('target changes raw X exactly10 and preserves YZAB including unwrappedB',()=>{const q=request(),target=p.target(q.expectedRaw);assert.deepEqual(target,{X:30,Y:30,Z:40,A:50,B:720});assert.equal(q.expectedRaw.X,20);});
test('reported precision accepted but saved pre-query discrepancy rejected',()=>{const q=request(),r={...q.expectedRaw,X:20.01,A:50.2};p.compareReported(r,q.expectedRaw,q.expectedDriver);const before={...q.expectedDriver,X:19};assert.throws(()=>p.compareReported(r,q.expectedRaw,before),/pre-query-driver/);assert.throws(()=>p.compareReported({...r,Z:40.03},q.expectedRaw,q.expectedDriver),/Z/);assert.throws(()=>p.compareReported({...r,B:0},q.expectedRaw,q.expectedDriver),/B/);});
test('exact request/start gate stays strict despite relaxed report-rounding gate',()=>{const q=request(),expected=p.target(q.expectedRaw);for(const axis of ['Y','Z','A','B']){const actual={...expected,[axis]:expected[axis]+0.01};assert.throws(()=>p.compareExact(actual,expected,'post'));}assert.throws(()=>p.compareReported({X:1},q.expectedRaw,q.expectedDriver),/Incomplete/);});

test('postmove model synchronization to rounded Y report is not mistaken for commanded Y motion',()=>{
 const before={X:241.27641236634807,Y:216.16071148488385,Z:26.5,A:200,B:720};
 const after={X:251.27641236634807,Y:216.16,Z:26.5,A:200,B:720};
 p.comparePostModel(after,p.target(before));
 const beforeFirmware={X:241.28,Y:216.16,Z:26.5,A:200,B:720};
 const afterFirmware={X:251.28,Y:216.16,Z:26.5,A:200,B:720};
 p.compareFirmwareStep(beforeFirmware,afterFirmware);
 assert.throws(()=>p.compareExact(after,p.target(before),'still-strict-start'),/Y/);
});
test('independent firmware step rejects nonX drift beyond precision, wrong X delta and B wrapping',()=>{
 const before={X:20,Y:30,Z:40,A:50,B:720},after=p.target(before);
 for(const [axis,delta] of [['Y',0.021],['Z',0.021],['A',0.301],['B',0.301],['X',0.021]]){
  const bad={...after,[axis]:after[axis]+delta};assert.throws(()=>p.compareFirmwareStep(before,bad));assert.throws(()=>p.comparePostModel(bad,after));
 }
 assert.throws(()=>p.compareFirmwareStep(before,{...after,B:0}));
 assert.throws(()=>p.compareFirmwareStep(before,{...after,X:before.X}));
 assert.throws(()=>p.compareFirmwareStep(before,{X:30}));
});
