'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../operator-console-native.js'),'utf8');
const arm=source.slice(source.indexOf(' function arm(){'),source.indexOf(' function disarm()'));
const P=require('../operator-console-policy.cjs');
function fixture(){
 const raw={X:10,Y:20,Z:57.75,A:200,B:-10},snap={raw,driver:{...raw},nativePoses:{}};
 const healthy={isShutdown:()=>false,isTerminated:()=>false,getCorePoolSize:()=>1,getMaximumPoolSize:()=>1,getActiveCount:()=>0,getQueue:()=>({isEmpty:()=>true})};
 let pending=true;const calls=[];
 const c={busy:false,latched:false,profile:{expectedRaw:{B:-10}},P:{validateProfile:()=>{},validateManualHandoff:P.validateManualHandoff},checkSources:()=>{},m:{isBusy:()=>false},field:()=>healthy,executor:{isShutdown:()=>true},gate:(...args)=>calls.push(['gate',...args]),ledger:()=>({entries:[],lastVerifiedRaw:{B:-10},usedAdditionalGrossDegrees:12}),snapshot:()=>snap,boundRaw:()=>{},armed:false,axes:{X:1,Y:1,Z:1,A:1,B:1},close:(a,b,t)=>assert(Math.abs(a-b)<=t),samePose:()=>{},append:(a,b)=>b.push(...a),CP:{responses:()=>{}},checkResponses:()=>{},d:{isMotionPending:()=>pending,receiveResponses:()=>[],waitForCompletion:()=>{calls.push(['M400']);pending=false;}},J:()=>({WaitForStillstand:'still'}),top:{},runRecord:{},transportUncertain:false,saveRecord:()=>{},collect:(_re,lines)=>lines.push('ok'),reported:r=>{assert.equal(r.B,-10);calls.push(['M114']);},acceptedSnapshot:null,lastApproach:{old:true},emit:()=>{},submit:(_label,body)=>{body.run();return'completed';}};
 vm.createContext(c);vm.runInContext(arm,c);return{c,healthy,calls};
}
{const {c,healthy,calls}=fixture();assert.equal(c.arm(),'completed');assert.equal(c.executor,healthy);assert.deepEqual(calls.filter(x=>['M400','M114'].includes(x[0])).map(x=>x[0]),['M400','M114']);assert(c.acceptedSnapshot);assert.equal(c.lastApproach,null);assert.equal(c.runRecord.manualPoseAdopted,true);}
{const {c}=fixture();c.ledger=()=>({entries:[],lastVerifiedRaw:{B:-11}});assert.throws(()=>c.arm(),/B changed/);assert.equal(c.acceptedSnapshot,null);}
{const {c,healthy}=fixture();healthy.getActiveCount=()=>1;assert.throws(()=>c.arm(),/healthy and idle/);}
console.log('native console idle-owner handoff/M400/manual-pose/B-continuity checks passed');
// Manual jog fractional model coordinates survive M114's two-decimal drivers.
{const {c}=fixture();const raw={X:359.19686795875464,Y:183.97952903288106,Z:32.25,A:200,B:-10};c.snapshot=()=>({raw,driver:{...raw,X:359.2,Y:183.98},nativePoses:{}});assert.equal(c.arm(),'completed');assert.equal(c.acceptedSnapshot.raw.X,raw.X);assert.equal(c.acceptedSnapshot.driver.X,359.2);}
// verify must retain the AFTER-query driver snapshot, not its pre-query copy.
{const verify=source.slice(source.indexOf(' function verify(expected){'),source.indexOf(' var recordDir='));const expected={X:359.19686795875464,Y:183.97952903288106,Z:32.25,A:200,B:-10};let queried=false;const c={axes:{X:1,Y:1,Z:1,A:1,B:1},snapshot:()=>({raw:{...expected},driver:queried?{...expected,X:359.2,Y:183.98}:{...expected},nativePoses:{}}),close:(a,b,t)=>assert(Math.abs(a-b)<=t),reported:()=>{queried=true;},lastSnapshot:null,acceptedSnapshot:null};vm.createContext(c);vm.runInContext(verify,c);c.verify(expected);assert.equal(c.acceptedSnapshot.driver.X,359.2);assert.equal(c.acceptedSnapshot.raw.X,expected.X);}
