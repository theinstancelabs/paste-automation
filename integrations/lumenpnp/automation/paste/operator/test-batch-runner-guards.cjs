'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync(require.resolve('../../scripts/Run_Paste_Operator_Batch.js'),'utf8');
const validate=src.slice(src.indexOf(' if(q.schema'),src.indexOf(' var api=null'));
function valid(q){vm.runInNewContext(validate,{q});}
const q={schema:1,enabled:true,id:'one-run',mode:'survey',references:['R1','R40']};valid(q);assert.throws(()=>valid({...q,id:'../replay'}));assert.throws(()=>valid({...q,references:['R1','R1']}));assert.throws(()=>valid({...q,enabled:false}));
const profileGuard=src.slice(src.indexOf(' if(!api||profileId'),src.indexOf(' if(api.status()'));
assert.throws(()=>vm.runInNewContext(profileGuard,{api:{},profileId:'old',q:{profileId:'new'}}),/Matching visible/);
let token=1;const context={api:{status:()=>({stopGeneration:token})},stopEpoch:1};vm.createContext(context);vm.runInContext(src.slice(src.indexOf('function notStopped(){'),src.indexOf('\n var dir=')),context);context.notStopped();token++;assert.throws(()=>context.notStopped(),/STOP/);
const noReplay=src.slice(src.indexOf(' var dir='),src.indexOf(' var report='));let mkdirCalls=0;assert.throws(()=>vm.runInNewContext(noReplay,{root:'/synthetic',q,F:function(){this.exists=()=>true;this.mkdirs=()=>{mkdirCalls++;return true;};}}),/no replay/);assert.equal(mkdirCalls,0);
console.log('Actual batch request/profile/STOP/no-replay guard blocks pass');
valid({...q,mode:'dispense-and-survey',conditioning:{references:['R3'],recipe:{doseDegrees:.25}}});
assert.throws(()=>valid({...q,mode:'dispense-and-survey',conditioning:{references:['R1'],recipe:{}}}),/overlapping/);
assert.throws(()=>valid({...q,mode:'dispense-and-survey',conditioning:{references:['R99'],recipe:{}}}),/Unknown/);
const settle=src.slice(src.indexOf('notStopped();java.lang.Thread.sleep(150);'),src.indexOf('var file=new F(dir,ref'));
let captures=0,stopped=false;const pose={X:1,Y:2,Z:32.25,A:0,B:0},settleContext={notStopped:()=>{if(stopped)throw Error('STOP');},java:{lang:{Thread:{sleep:ms=>assert.equal(ms,150)}}},before:{raw:pose},api:{status:()=>({raw:pose,busy:false})},m:{isBusy:()=>false},camera:{capture:()=>{captures++;return 'image'+captures;}}};vm.runInNewContext(settle,settleContext);assert.equal(captures,2);assert.equal(settleContext.image,'image2');captures=0;settleContext.api.status=()=>({raw:{...pose,X:2},busy:false});assert.throws(()=>vm.runInNewContext(settle,settleContext),/settle/);assert.equal(captures,0);
