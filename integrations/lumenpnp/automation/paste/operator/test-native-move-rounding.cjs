'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../operator-console-native.js'),'utf8');
const verify=source.slice(source.indexOf(' function verify(expected){'),source.indexOf(' var recordDir='));
const move=source.slice(source.indexOf(' function move(axis,target'),source.indexOf(' function zPath(target)'));
function fixture(error=0,bStart=-4647.48){
 let raw={X:359.19686795875464,Y:183.97952903288106,Z:32.25000000000002,A:200,B:bStart};
 const project=r=>({top:{x:r.X,y:r.Y,z:0,rotation:-2.026918082244961}});
 const c={stationaryPurgeAnchor:null,axes:{X:'X',Y:'Y',Z:'Z',A:'A',B:'B'},profile:{rawBounds:Object.fromEntries(['X','Y','Z','A','B'].map(k=>[k,{min:-10000,max:10000}]))},snapshot:()=>({raw:{...raw},driver:{...raw},nativePoses:project(raw)}),gate:()=>{},boundRaw:project,stageTarget:(r,a,t)=>({...r,[a]:t}),close:(a,b,t,label)=>assert(Math.abs(a-b)<=t,label+': '+a+' vs '+b),samePose:(a,b,t)=>{for(const h in a)for(const k in a[h])assert(Math.abs(a[h][k]-b[h][k])<=t);},reported:()=>{},lastSnapshot:null,acceptedSnapshot:null,AL:function(a,t){this.axis=a;this.target=t;},planner:{moveTo:(_top,loc)=>{raw[loc.axis]=loc.target;for(const a of ['X','Y','Z','A','B'])raw[a]=Math.round(raw[a]*100)/100;raw.Y+=error;}},top:{},MO:{SpeedOverPrecision:1},runRecord:{stages:[]},saveRecord:()=>{},stopFlag:{get:()=>false},liftingToSafe:false};
 vm.createContext(c);vm.runInContext(verify+move,c);return c;
}
{const c=fixture();assert.equal(c.move('X',349.2,1,'camera-target',0),true);assert.equal(c.acceptedSnapshot.raw.Y,183.98);assert.equal(c.runRecord.stages[0].verified,true);assert.equal(c.acceptedSnapshot.raw.B,-4647.48);}
{const c=fixture(.02);assert.throws(()=>c.move('X',349.2,1,'camera-target',0),/raw Y/);assert.equal(c.runRecord.stages[0].verified,false);}
console.log('actual native move+verify held-axis report rounding regression passed');

{const c=fixture(0,87.97308191775504);assert.equal(c.move('X',349.2,1,'camera-target',0),true);assert.equal(c.acceptedSnapshot.raw.B,87.97);}
