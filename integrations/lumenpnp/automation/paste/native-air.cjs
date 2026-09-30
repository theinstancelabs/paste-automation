/* Pure ES5 native-air sequencing. No serial, files, Java, or machine access. */
(function(root){'use strict';
function fail(s){throw Error(s);}
function finite(n,label){if(typeof n!=='number'||!isFinite(n))fail(label+' must be finite');return n;}
function axes(p){if(!p||Object.keys(p).sort().join(',')!=='A,B,X,Y,Z')fail('Exact five-axis snapshot required');['X','Y','Z','A','B'].forEach(function(k){finite(p[k],k);});}
function copy(p){var r={};['X','Y','Z','A','B'].forEach(function(k){r[k]=p[k];});return r;}
function unchanged(a,b){['Z','A','B'].forEach(function(k){if(Math.abs(a[k]-b[k])>1e-9)fail('Air target changes raw '+k);});}
function context(c){if(!c)fail('Native state required');['enabled','homed','jobStopped','emptyHeads','quarantined','ownedTask','plannerEmpty','driverNotPending','subordinateEmpty','completionRegexAbsent'].forEach(function(k){if(c[k]!==true)fail('Unsafe native state: '+k);});if(c.minimumSpeed!==0.05)fail('Audited native minimum speed changed');}
function segments(spec){
 axes(spec.startRaw);if(!spec.targets||!spec.targets.length||spec.targets.length>10000)fail('Bounded nonempty raw targets required');
 if(JSON.stringify(spec.axisOrder)!=='["X","Y"]'&&JSON.stringify(spec.axisOrder)!=='["Y","X"]')fail('Explicit one-axis XY path order required');
 finite(spec.speedFraction,'speedFraction');if(spec.minimumSpeed!==0.05||spec.speedFraction<spec.minimumSpeed||spec.speedFraction>0.1)fail('Requested speed must avoid native clamping and stay <=0.1');
 finite(spec.maxSegmentMm,'maxSegmentMm');if(spec.maxSegmentMm<=0||spec.maxSegmentMm>10)fail('Measured/reviewed segments must be >0 and <=10mm');
 var result=[],at=copy(spec.startRaw);
 spec.targets.forEach(function(target,pointIndex){axes(target);unchanged(target,spec.startRaw);
  var first=result.length;
  spec.axisOrder.forEach(function(axis){var start=at[axis],delta=target[axis]-start,steps=Math.ceil(Math.abs(delta)/spec.maxSegmentMm);
   for(var i=1;i<=steps;i++){var to=copy(at);to[axis]=i===steps?target[axis]:start+delta*i/steps;
    result.push({axis:axis,from:copy(at),to:to,pointIndex:pointIndex,pointComplete:false});at=copy(to);if(result.length>20000)fail('Air path exceeds bounded segment count');}
  });
  if(result.length>first)result[result.length-1].pointComplete=true;
  else result.push({axis:null,from:copy(at),to:copy(at),pointIndex:pointIndex,pointComplete:true});
  if(result.length>20000)fail('Air path exceeds bounded segment count');
 });return result;
}
function verifyStep(before,after,segment){axes(before);axes(after);axes(segment.from);axes(segment.to);['X','Y','Z','A','B'].forEach(function(k){var tolerance=(k==='A'||k==='B')?0.3:0.02;var expected=k===segment.axis?segment.to[k]:before[k];if(Math.abs(before[k]-segment.from[k])>tolerance||Math.abs(after[k]-expected)>tolerance||Math.abs((after[k]-before[k])-(segment.to[k]-segment.from[k]))>tolerance)fail('Independent firmware step mismatch '+k);});}
function session(s,now){
 var n=s&&s.nativeExecution;if(!n||n.schema!==1||n.scope!=='joint-clearance-single-raw-XY-air'||n.pathClearanceReviewed!==true)fail('Reviewed native air session required');
 ['pathClearanceRecord','rawSegmentsSha256'].forEach(function(k){if(typeof n[k]!=='string'||!n[k].trim())fail(k+' required');});
 if(!/^[a-f0-9]{64}$/.test(n.rawSegmentsSha256))fail('Exact reviewed raw segment hash required');
 axes(n.expectedRaw);axes(n.expectedDriver);
 ['N1','N2','top','bottom'].forEach(function(k){if(!n.expectedNativePoses||!n.expectedNativePoses[k])fail('All native poses required');['x','y','z','rotation'].forEach(function(a){finite(n.expectedNativePoses[k][a],k+' '+a);});});
 var e=n.clearanceEvidence;if(!e||typeof e.path!=='string'||e.path.charAt(0)!=='/'||!/^[a-f0-9]{64}$/.test(e.sha256))fail('Fresh clearance image required');
 finite(e.capturedMs,'clearance image time');if(e.capturedMs>s.createdMs||now-e.capturedMs>300000)fail('Clearance image stale/future');
 finite(n.maxSegmentMm,'maxSegmentMm');if(n.maxSegmentMm<=0||n.maxSegmentMm>10)fail('Reviewed segment size required');
 return n;
}
function run(spec,io){
 var path=segments(spec),state={completedSegments:0,completedPoints:0,motionAttempted:false,positionVerified:false,finished:false};
 io.claim();
 try{
  context(io.state());io.preflight(path);io.boundary(spec.startRaw);state.positionVerified=true;io.record('preflight-complete-at-joint-clearance',state);
  var stop=function(){var action=io.control();if(action!==null&&action!==undefined&&action!=='pause'&&action!=='cancel')fail('Invalid air control');if(action){state.finished=true;state.stop=action;io.record(action==='pause'?'paused-at-clearance-new-plan-required':'cancelled-at-clearance',state);return true;}return false;};
  if(stop())return state;
  for(var i=0;i<path.length;i++){
   var segment=path[i];context(io.state());
   if(segment.axis!==null){state.motionAttempted=true;state.positionVerified=false;io.record('moving-single-raw-'+segment.axis,state);io.move(segment);io.verify(segment);state.positionVerified=true;state.completedSegments++;}
   if(segment.pointComplete)state.completedPoints=segment.pointIndex+1;
   io.record('verified-joint-clearance-boundary',state);if(stop())return state;
  }
  state.finished=true;io.record('completed-air-software',state);return state;
 }catch(error){io.fault(error,state);throw error;}
}
var api={nativeErrorRegex:"(?i).*(?:\\berror\\s*:|!!|\\bstart\\b|reset|disconnect|\\bresend\\s*:|\\brs\\s+N?\\d|unknown command|halted|fatal|\\bkilled\\b).*",session:session,segments:segments,context:context,verifyStep:verifyStep,run:run};if(typeof module!=='undefined')module.exports=api;else root.NativePasteAir=api;
})(this);
