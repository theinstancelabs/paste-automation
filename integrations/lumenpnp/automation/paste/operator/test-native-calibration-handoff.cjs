'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),P=require('../operator-console-policy.cjs');
const src=fs.readFileSync(require.resolve('../operator-console-native.js'),'utf8');
function section(a,b){return src.slice(src.indexOf(a),src.indexOf(b));}
const code=section(' function arm(){',' function disarm()')+section(' function approach(ref,pad,rawZ){',' function verifyVacuumReference(')+section(' function recordNeedleTouchPoint(ref,pad){',' function applyNeedleTouches(')+section(' function afterManualHandoff(fn){',' function initChecks()');
let raw={X:20,Y:20,Z:62.4,A:200,B:-10};const zMoves=[];
const owner={isShutdown:()=>false,isTerminated:()=>false,getCorePoolSize:()=>1,getMaximumPoolSize:()=>1,getActiveCount:()=>0,getQueue:()=>({isEmpty:()=>true})};
const c={busy:false,latched:false,armed:true,handoffRunning:false,profile:{workZ:60,calibrationRawZMax:63,safeZ:32.25,pads:{R15:{'1':{tipXY:[20,20]}},R40:{'1':{tipXY:[30,30]}}}},P:{validateProfile:()=>{},validateManualHandoff:P.validateManualHandoff},checkSources:()=>{},m:{isBusy:()=>false},field:()=>owner,executor:owner,gate:()=>{},ledger:()=>({entries:[],lastVerifiedRaw:{B:-10}}),snapshot:()=>({raw:{...raw},driver:{...raw},nativePoses:{}}),boundRaw:r=>assert(r.Z<=63&&r.Z>=32.25),calibrationZLimit:()=>63,axes:{X:1,Y:1,Z:1,A:1,B:1},close:(a,b,t)=>assert(Math.abs(a-b)<=t),samePose:()=>{},d:{isMotionPending:()=>false},reported:()=>{},acceptedSnapshot:null,lastApproach:{ref:'R15',pad:'1',tipXY:[20,20],rawZ:55},emit:()=>{},runRecord:{},submit:(_label,body)=>{c.runRecord={};body.run();return{get:()=>null};},calibration:{alignmentApplied:true,ztouchSamples:[]},replaceSample:(ss,p)=>[...ss.filter(s=>s.ref!==p.ref),p],verify:()=>c.snapshot(),calibrationSave:()=>{},calibrationStatus:()=>({}),stageTarget:(r,a,t)=>({...r,[a]:t}),zPath:z=>{zMoves.push(z);raw.Z=z;return true;},xy:(x,y)=>{raw.X=x;raw.Y=y;return true;},java:{lang:{System:{currentTimeMillis:()=>0},Thread:{sleep:()=>{}}}},J:name=>name==='java.lang.Thread'?function(r){this.setDaemon=()=>{};this.start=()=>r.run();}:function(r){return r;}};
vm.createContext(c);vm.runInContext(code,c);
c.afterManualHandoff(()=>c.recordNeedleTouchPoint('R15','1'));
assert.equal(c.calibration.ztouchSamples.length,1);assert.equal(c.calibration.ztouchSamples[0].rawZ,62.4);assert.equal(c.calibration.ztouchSamples[0].operatorConfirmedBarelyTouching,true);
c.afterManualHandoff(()=>c.approach('R40','1',55));
assert.deepEqual(zMoves,[32.25,55]);assert.equal(raw.Z,55);assert.equal(raw.B,-10);assert.equal(c.lastApproach.ref,'R40');assert.equal(c.lastApproach.rawZ,55);
console.log('real arm→R15 manual touch62.4 capture→R40 safe-lift/approach55 flow passed with workZ60/calibration63');
