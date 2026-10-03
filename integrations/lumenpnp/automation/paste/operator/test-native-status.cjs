'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync(require.resolve('../operator-console-native.js'),'utf8');const a=src.indexOf(' function status(){'),b=src.indexOf(' function arm(',a);const raw={X:334.85,Y:157,Z:32.25,A:200,B:-7090};let connected=true;
const d={}; // GcodeDriver has protected connected, and NO isConnected() method.
const c={snapshot:()=>({raw,driver:raw,nativePoses:{}}),stopGeneration:3,handoffRunning:false,busy:false,armed:true,latched:false,m:{isBusy:()=>false,isEnabled:()=>true,isHomed:()=>true},liveConfigHash:()=> 'hash',d,field:(type,name,obj)=>{assert.equal(type,'org.openpnp.machine.reference.driver.GcodeDriver');assert.equal(name,'connected');assert.equal(obj,d);return connected;},panelState:{get:()=> 'Stopped'},panel:{},runRecord:{id:'completed-camera'}};
vm.createContext(c);vm.runInContext(src.slice(a,b),c);let s=c.status();assert.equal(s.connected,true);assert.equal(s.error,undefined);assert.equal(s.raw,raw);assert.equal(s.lastRecord,'completed-camera');assert.equal(s.stopGeneration,3);assert.equal(s.armed,true);connected=false;assert.equal(c.status().connected,false);
console.log('Actual status() returns runner-required pose/record/stop fields using GcodeDriver protected connected field');
