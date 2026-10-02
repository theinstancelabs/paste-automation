'use strict';
// Linear M114 counts may use a post-home coordinate origin. Validate motion
// from signed count deltas, independent of the absolute raw-coordinate origin.
(function(root){
function fail(message){throw Error(message);}
var scales={X:320,Y:320,Z:40};
function compare(before,after,stage){
 if(!before||!after||!stage||!stage.startRaw||!stage.targetRaw)fail('Linear count comparison inputs required');
 if(!scales[stage.axis])fail('Linear controller axis must be X, Y or Z');
 ['X','Y','Z','A','B'].forEach(function(axis){
  [before[axis],after[axis]].forEach(function(value){if(typeof value!=='number'||!isFinite(value)||Math.floor(value)!==value||Math.abs(value)>9007199254740991)fail('Linear count must be a finite safe integer: '+axis);});
  if(axis!==stage.axis&&before[axis]!==after[axis])fail('Other controller axis count changed in '+stage.axis+' stage');
 });
 var scale=scales[stage.axis];
 if(!scale)fail('Linear controller axis must be X, Y or Z');
 var start=stage.startRaw[stage.axis],target=stage.targetRaw[stage.axis];
 if(typeof start!=='number'||!isFinite(start)||typeof target!=='number'||!isFinite(target))fail('Linear stage coordinates must be finite');
 var expected=(target-start)*scale,observed=after[stage.axis]-before[stage.axis];
 if(!isFinite(expected)||Math.abs(observed-expected)>1+1e-9)fail('Linear controller count delta mismatch');
 return {axis:stage.axis,scale:scale,expectedSignedDelta:expected,observedSignedDelta:observed,maximumRoundingErrorSteps:1};
}
var api={compare:compare};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.PasteContiguousLinearCounts=api;
})(this);
