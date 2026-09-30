/* ES5 stationary free-air recording contract; no pressure acceptance thresholds. */
(function(root){'use strict';
function fail(s){throw Error(s);}
function finite(v,label){if(typeof v!=='number'||!isFinite(v))fail(label+' must be finite');return v;}
function integer(v,low,high,label){finite(v,label);if(Math.floor(v)!==v||v<low||v>high)fail(label+' outside bounded sampling contract');}
function validate(q,now,jvm){
 if(!q||q.schema!==1||q.scope!=='stationary-N1-VAC1-free-air-baseline')fail('Stationary baseline request required');
 if(typeof q.id!=='string'||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(q.id))fail('Fresh baseline UUID required');
 finite(q.createdMs,'createdMs');if(q.createdMs>now||now-q.createdMs>300000||q.jvmStartMs!==jvm)fail('Stale or different JVM baseline request');
 if(typeof q.operator!=='string'||!q.operator.trim()||typeof q.expectedLeftTipId!=='string'||!q.expectedLeftTipId.trim())fail('Operator and exact installed N1 tip identity required');
 if(typeof q.liveConfigurationSha256!=='string'||!/^[a-f0-9]{64}$/.test(q.liveConfigurationSha256))fail('Exact live configuration digest required');
 ['operatorVerifiedFreeAir','emptyNozzlesObserved','bothHeadsClear','motionAreaClear'].forEach(function(k){if(q[k]!==true)fail(k+' required');});
 var image=q.stationaryEvidence;if(!image||typeof image.path!=='string'||image.path.charAt(0)!=='/'||!/^[a-f0-9]{64}$/.test(image.sha256))fail('Fresh reviewed stationary image required');
 finite(image.capturedMs,'capturedMs');if(image.capturedMs>q.createdMs||now-image.capturedMs>300000)fail('Stationary image stale/future');
 ['expectedRaw','expectedDriver'].forEach(function(k){if(!q[k]||Object.keys(q[k]).sort().join(',')!=='A,B,X,Y,Z')fail('Five-axis snapshot required');Object.keys(q[k]).forEach(function(a){finite(q[k][a],k+' '+a);});});
 ['N1','N2','top','bottom'].forEach(function(k){if(!q.expectedNativePoses||!q.expectedNativePoses[k])fail('All native poses required');['x','y','z','rotation'].forEach(function(a){finite(q.expectedNativePoses[k][a],k+' '+a);});});
 integer(q.sampleCountPerPhase,3,20,'sampleCountPerPhase');integer(q.settleMs,100,2000,'settleMs');integer(q.sampleIntervalMs,50,500,'sampleIntervalMs');integer(q.maxDurationMs,5000,60000,'maxDurationMs');
 if(2*q.settleMs+2*q.sampleCountPerPhase*q.sampleIntervalMs>=q.maxDurationMs)fail('Sampling schedule exceeds duration');
 return q;
}
function commandContract(actuate,read,regex,ack){
 function lines(text){return String(text).split(/\r?\n/).map(function(line){return line.split(';')[0].trim().replace(/\s+/g,' ');}).filter(function(line){return line.length;});}
 if(JSON.stringify(lines(actuate))!==JSON.stringify(['{True:M106 P1 S180}{False:M107 P1}','{True:M106}{False:M107}']))fail('VAC1 boolean template changed');
 if(JSON.stringify(lines(read))!==JSON.stringify(['M260 A112 B1 S1','M260 A109 B6 S1','M261 A109 B1 S2']))fail('VAC1 sensor template changed');
 if(String(regex).trim()!=='^.*data:(?<Value>.*)'||String(ack).trim()!=='^ok.*')fail('VAC1 sensor/ACK regex changed');
}
function actuationLines(on){if(typeof on!=='boolean')fail('Boolean VAC1 state required');return on?['M106 P1 S180','M106']:['M107 P1','M107'];}
function sensorLines(){return ['M260 A112 B1 S1','M260 A109 B6 S1','M261 A109 B1 S2'];}
function allowedLine(line){return ['M106 P1 S180','M106','M107 P1','M107','M260 A112 B1 S1','M260 A109 B6 S1','M261 A109 B1 S2'].indexOf(line)>=0;}
function pressure(lines,required){var values=[];lines.forEach(function(line){var m=/data:(.*)$/.exec(String(line));if(m)values.push(parseSample(m[1]));});if(values.length>1||(required&&values.length!==1)||(!required&&values.length))fail('Unexpected/missing pressure response');return values.length?values[0]:null;}
function parseSample(raw){var text=String(raw).trim();if(!/^\d{1,3}$/.test(text))fail('Vacuum sensor did not return one decimal byte');var value=Number(text);if(value>255)fail('Vacuum sensor byte outside protocol range');return value;}
function summary(samples){if(!samples.length)fail('Samples required');var sum=0,min=255,max=0;samples.forEach(function(s){var v=parseSample(s.value);sum+=v;min=Math.min(min,v);max=Math.max(max,v);});return {count:samples.length,min:min,max:max,mean:sum/samples.length,spread:max-min,acceptanceEstablished:false};}
// A fault skips all subsequent operations, including final off. That is a
// deliberate no-retry rule: an uncertain connection needs separate recovery.
function sequence(q,io){var start=io.now(),result={off:[],on:[]};
 function bound(){if(io.now()-start>q.maxDurationMs)fail('Baseline duration exceeded; no subsequent command');}
 function act(v){bound();io.actuate(v);bound();}
 function wait(ms){bound();io.sleep(ms);bound();}
 act(false);wait(q.settleMs);
 ['off','on'].forEach(function(phase){if(phase==='on'){act(true);wait(q.settleMs);}
  for(var i=0;i<q.sampleCountPerPhase;i++){bound();var raw=io.read(),value=parseSample(raw);bound();var sample={value:value,raw:String(raw),elapsedMs:io.now()-start};result[phase].push(sample);io.record(phase,sample);if(i+1<q.sampleCountPerPhase)wait(q.sampleIntervalMs);}
 });
 act(false);result.finalOffAcknowledged=true;result.offSummary=summary(result.off);result.onSummary=summary(result.on);return result;
}
var api={commandContract:commandContract,actuationLines:actuationLines,sensorLines:sensorLines,allowedLine:allowedLine,pressure:pressure,validate:validate,parseSample:parseSample,summary:summary,sequence:sequence};if(typeof module!=='undefined')module.exports=api;else root.PasteVacuumBaseline=api;
})(this);
