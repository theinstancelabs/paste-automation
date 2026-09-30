const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const p=require('./vacuum-baseline.cjs');
function request(){const q=JSON.parse(fs.readFileSync(__dirname+'/vacuum-baseline.pending.json'));Object.assign(q,{id:'12345678-1234-1234-1234-123456789abc',createdMs:1000,jvmStartMs:42,operator:'synthetic operator',expectedLeftTipId:'synthetic-tip',liveConfigurationSha256:'a'.repeat(64),operatorVerifiedFreeAir:true,emptyNozzlesObserved:true,bothHeadsClear:true,motionAreaClear:true,stationaryEvidence:{path:'/synthetic/image.jpg',sha256:'b'.repeat(64),capturedMs:900}});for(const k of ['expectedRaw','expectedDriver'])q[k]={X:1,Y:2,Z:3,A:4,B:720};for(const k of ['N1','N2','top','bottom'])q.expectedNativePoses[k]={x:1,y:2,z:3,rotation:4};return q;}
function io(){let now=0;const events=[];return {events,now:()=>now,sleep:ms=>{now+=ms;},actuate:v=>events.push(v),read:()=> ' 82 ',record:(phase,s)=>events.push(phase),late:()=>{now+=40000;}};}
test('pending baseline cannot authorize actuation; exact identity/freshness/empty freeair required',()=>{assert.throws(()=>p.validate(JSON.parse(fs.readFileSync(__dirname+'/vacuum-baseline.pending.json')),1001,42));p.validate(request(),1001,42);for(const change of [q=>q.expectedLeftTipId=null,q=>q.operatorVerifiedFreeAir=false,q=>q.emptyNozzlesObserved=false,q=>q.stationaryEvidence.capturedMs=-300000,q=>q.expectedRaw.B=null,q=>q.jvmStartMs=43]){const q=request();change(q);assert.throws(()=>p.validate(q,1001,42));}});
test('counts/timing bounded, no pressure thresholds or calibration from samples',()=>{for(const [k,v] of [['sampleCountPerPhase',0],['sampleCountPerPhase',21],['settleMs',-1],['sampleIntervalMs',0],['maxDurationMs',60001]]){const q=request();q[k]=v;assert.throws(()=>p.validate(q,1001,42));}const s=p.summary([{value:80},{value:84}]);assert.deepEqual(s,{count:2,min:80,max:84,mean:82,spread:4,acceptanceEstablished:false});});
test('strict singlebyte sensor parsing refuses malformed/error/nonfinite values',()=>{for(const v of ['',null,'NaN','Error:82','1 2','256','-1','82.5'])assert.throws(()=>p.parseSample(v));assert.equal(p.parseSample(' 082 '),82);});
test('successful sequence records separate off/on phases and final acknowledged off',()=>{const q=request(),x=io(),r=p.sequence(q,x);assert.deepEqual(x.events.filter(x=>typeof x==='boolean'),[false,true,false]);assert.equal(r.off.length,8);assert.equal(r.on.length,8);assert.equal(r.finalOffAcknowledged,true);});
test('read fault while on stops without retry or blind off command',()=>{const x=io();let count=0;x.read=()=>{if(++count===9)throw Error('disconnect');return '82';};assert.throws(()=>p.sequence(request(),x),/disconnect/);assert.deepEqual(x.events.filter(x=>typeof x==='boolean'),[false,true]);});
test('actuation fault or delayed read prevents every subsequent operation',()=>{const x=io();x.actuate=v=>{x.events.push(v);throw Error('reset');};assert.throws(()=>p.sequence(request(),x),/reset/);assert.deepEqual(x.events,[false]);const y=io();y.read=()=>{y.late();return '82';};assert.throws(()=>p.sequence(request(),y),/duration/);assert.deepEqual(y.events,[false]);});
test('exact configured VAC1 templates only, no arbitrary line or altered PWM',()=>{
 const act='{True:M106 P1 S180}{False:M107 P1};\n{True:M106}{False:M107};',read='M260 A112 B1 S1 ; multiplexer\nM260 A109 B6 S1\nM261 A109 B1 S2';
 p.commandContract(act,read,'^.*data:(?<Value>.*)','^ok.*');
 assert.throws(()=>p.commandContract(act.replace('180','255'),read,'^.*data:(?<Value>.*)','^ok.*'));
 assert.throws(()=>p.commandContract(act,read.replace('B1 S1','B2 S1'),'^.*data:(?<Value>.*)','^ok.*'));
 for(const x of ['G0 X1','G92 B0','M906 B400','M106 P2 S180','M114'])assert.equal(p.allowedLine(x),false);
 assert.deepEqual(p.actuationLines(true),['M106 P1 S180','M106']);assert.deepEqual(p.actuationLines(false),['M107 P1','M107']);
 assert.throws(()=>p.actuationLines('true'));
});
test('unexpected/multiple/malformed pressure lines fail; single data may precede ACK',()=>{
 assert.equal(p.pressure(['data: 82','ok'],true),82);
 for(const [lines,required] of [[['ok'],true],[['data:82'],false],[['data:82','data:83'],true],[['data:1 2'],true]])assert.throws(()=>p.pressure(lines,required));
});
