'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict');
const src=fs.readFileSync(require.resolve('../operator-console-native.js'),'utf8');
const fn=src.slice(src.indexOf(' function xy('),src.indexOf(' function saveRecord')).trim();
function run(start,target,stopAfter=Infinity){
 const raw={...start},moves=[];
 const xy=new Function('snapshot','move','close','return ('+fn+');')(
  ()=>({raw:{...raw}}),(axis,value,speed)=>{assert(Math.abs(value-raw[axis])<=10.000001);assert.equal(speed,1);raw[axis]=value;moves.push([axis,value]);return moves.length<stopAfter;},
  (a,b,t)=>assert(Math.abs(a-b)<=t));
 return {ok:xy(...target,'test'),raw,moves};
}
for(const [start,target] of [[{X:359.19686795875464,Y:183.97952903288106},[385,220]],[{X:359.19686795875464,Y:183.97952903288106},[325,150]],[{X:347.6,Y:142.66},[334.65,155.995]],[{X:1,Y:1},[31.12,-15.2]],[{X:0,Y:0},[10,10]],[{X:1,Y:1},[1,1]]]){
 const r=run(start,target);assert(r.ok);assert.equal(r.raw.X,Math.round(target[0]*100)/100);assert.equal(r.raw.Y,Math.round(target[1]*100)/100);
}
const stopped=run({X:0,Y:0},[30,30],1);assert.equal(stopped.ok,false);assert.equal(stopped.moves.length,1);
console.log('native camera XY endpoint/segment/stop regressions passed');
