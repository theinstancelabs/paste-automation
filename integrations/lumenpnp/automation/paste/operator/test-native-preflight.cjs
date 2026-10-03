'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../operator-console-native.js'),'utf8');
const submit=source.slice(source.indexOf(' function submit(label,body){'),source.indexOf(' function status()'));
let machineBusy=false,shutdown=false;const events=[];
const ex={isShutdown:()=>false,isTerminated:()=>false,getActiveCount:()=>machineBusy?1:0,getQueue:()=>({isEmpty:()=>true}),submit:task=>task.call(),shutdown:()=>{shutdown=true;}};
// Simulate native executor reporting its owned active task after submission.
let submitted=false;ex.getActiveCount=()=>submitted?1:0;ex.submit=task=>{submitted=true;return task.call();};
const c={armed:true,busy:false,latched:false,runRecord:{id:'old-success',motionSubmitted:true,controllerQuerySubmitted:true},m:{isBusy:()=>machineBusy,fireMachineBusy:v=>{machineBusy=v;}},executor:ex,stopFlag:{set:()=>{}},emit:e=>events.push(e),Callable:function(x){return x;},Thread:{currentThread:()=>({})},taskOwner:()=>{},ownedTask:false,keepBusy:false,transportUncertain:false,liftingToSafe:false,gate:()=>{throw Error('Prior manual motion pending; use Connect/check controller before console motion');},print:()=>{}};
vm.createContext(c);vm.runInContext(submit,c);c.submit('new-preflight',{run:()=>assert.fail('Must not execute')});
assert.equal(c.runRecord,null);assert.equal(c.latched,false);assert.equal(c.busy,false);assert.equal(c.keepBusy,false);assert.equal(shutdown,false);assert.equal(machineBusy,false);assert(events.some(e=>e.error&&e.error.includes('Connect/check')));
console.log('fresh preflight failure never inherits prior completed motion or quarantines owner');
