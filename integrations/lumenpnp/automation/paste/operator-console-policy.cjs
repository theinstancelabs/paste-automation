'use strict';
// Small, DOM/Node/Nashorn-compatible policy shared by the supervised UI backend.
(function(root){
function fail(s){throw new Error(s);}
function finite(v,n){if(typeof v!=='number'||!isFinite(v))fail(n+' must be finite');return v;}
function grid(v,step,n){finite(v,n);if(Math.abs(v/step-Math.round(v/step))>1e-8)fail(n+' is off the '+step+' grid');return v;}
function uuid(v){return typeof v==='string'&&/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(v);}
function axisObject(v,n){if(!v||Object.keys(v).sort().join(',')!=='A,B,X,Y,Z')fail(n+' must contain exact XYZAB');Object.keys(v).forEach(function(k){finite(v[k],n+'.'+k);});}
function profile(p){
 if(!p||p.schema!==1||!/^([a-f0-9]{64}|[a-f0-9-]{36})$/i.test(p.id||'')||!uuid(p.sessionId)||typeof p.name!=='string'||!p.name)fail('Operator profile identity required');
 finite(p.jvmStartMs,'jvmStartMs');if(!/^[a-f0-9]{64}$/.test(p.liveConfigurationSha256||''))fail('Configuration hash required');
 if(p.safeZ!==32.25||p.travelZ!==53.45||typeof p.workZ!=='number'||!isFinite(p.workZ)||p.workZ<55||p.workZ>63)fail('Reviewed 32.25/53.45/55..63 Z profile required');
 finite(p.gapUncertaintyMm,'gapUncertaintyMm');if(p.gapUncertaintyMm<0)fail('Nonnegative surface uncertainty required');
 if(!p.rawBounds||!p.headClearanceBounds||!p.pads||!Array.isArray(p.sourceEvidence)||!p.sourceEvidence.length)fail('Raw/head bounds, job pad table and source hashes required');
 axisObject(p.expectedRaw,'expectedRaw');axisObject(p.expectedDriver,'expectedDriver');
 if(!p.expectedNativePoses||Object.keys(p.expectedNativePoses).sort().join(',')!=='N1,N2,bottom,top')fail('Expected native head/camera poses required');
 ['N1','N2','top','bottom'].forEach(function(h){['x','y','z','rotation'].forEach(function(k){finite(p.expectedNativePoses[h][k],h+'.'+k);});});
 if(Math.abs(p.expectedRaw.Z-p.safeZ)>0.0001)fail('Profile must be captured at both-head safe Z');
 ['X','Y','Z','A','B'].forEach(function(a){var b=p.rawBounds[a];if(!b||finite(b.min,'rawBounds.'+a+'.min')>finite(b.max,'rawBounds.'+a+'.max'))fail('Ordered raw bounds required: '+a);});
 if(p.rawBounds.Z.max>63||p.workZ>p.rawBounds.Z.max||p.workZ<p.rawBounds.Z.min)fail('Work Z must remain inside explicit profile raw bounds (maximum 63 mm)');
 if(p.calibrationRawZMax!==undefined&&(finite(p.calibrationRawZMax,'Calibration Z ceiling')<p.workZ||p.calibrationRawZMax>p.rawBounds.Z.max||p.calibrationRawZMax>63))fail('Calibration Z ceiling must be within explicit raw bounds and at least workZ');
 ['N1','N2'].forEach(function(h){var b=p.headClearanceBounds[h];if(!b)fail('Both-head bounds missing '+h);['minX','maxX','minY','maxY','minZ','maxZ'].forEach(function(k){finite(b[k],h+'.'+k);});});
 var refs=Object.keys(p.pads);if(!refs.length)fail('Registered resistor pad map required');
 refs.forEach(function(ref){if(!/^R(?:[1-9]|[1-3][0-9]|40)$/.test(ref))fail('Only resistor references R1..R40 accepted');['1','2'].forEach(function(k){var t=p.pads[ref][k];if(!t||!Array.isArray(t.cameraXY)||t.cameraXY.length!==2||!Array.isArray(t.tipXY)||t.tipXY.length!==2)fail('Camera/tip XY arrays required for '+ref+'.'+k);finite(t.cameraXY[0],ref+'.'+k+'.cameraXY.X');finite(t.cameraXY[1],ref+'.'+k+'.cameraXY.Y');finite(t.tipXY[0],ref+'.'+k+'.tipXY.X');finite(t.tipXY[1],ref+'.'+k+'.tipXY.Y');if(!((p.vacuumReference||p.heightCalibrationPending===true)&&t.gapAtWorkZ===null))finite(t.gapAtWorkZ,ref+'.'+k+'.gapAtWorkZ');if(p.needleTouchCalibrated===true)finite(t.touchRawZ,'Confirmed touch plane '+ref+'.'+k);if(!p.vacuumReference&&p.needleTouchCalibrated!==true&&p.heightCalibrationPending!==true&&t.gapAtWorkZ-p.gapUncertaintyMm<0.1-1e-9)fail('Current work-Z gap lower bound is below 0.10 mm at '+ref+'.'+k);});});
 if(!p.rodBudget||finite(p.rodBudget.baselineGrossDegrees,'rod baseline gross')<0||finite(p.rodBudget.maximumAdditionalGrossDegrees,'rod additional budget')<1||p.rodBudget.maximumAdditionalGrossDegrees>20000||finite(p.rodBudget.baselineB,'rod baseline B')!==p.expectedRaw.B)fail('Hash-bound conservative 41 mm planning budget required');
 return p;
}
function recipe(r,p){
 if(!r||['both','1','2'].indexOf(r.padMode)<0)fail('Pad mode must be both, 1 or 2');
 if(r.heightMode!==undefined&&['raw','gap'].indexOf(r.heightMode)<0)fail('Height mode must be raw or gap');
 if(r.heightMode==='gap'&&(finite(r.gapMm,'Needle gap')<.15||r.gapMm>1))fail('Needle gap must be 0.15..1 mm');
 if(grid(r.doseDegrees,0.01,'Dose')<0.25||r.doseDegrees>30)fail('Dose must be 0.25..30 degrees on 0.01 grid');
 if(grid(r.retractPercent,5,'Inter-resistor retract')<0||r.retractPercent>50)fail('Inter-resistor retract must be 0..50% in 5% increments');
 if(grid(r.dwellMs,100,'Dose dwell')<0||r.dwellMs>5000)fail('Dose dwell must be 0..5000 ms in 100 ms increments');
 if(grid(r.retractDwellMs,100,'Retract dwell')<0||r.retractDwellMs>2000)fail('Retract dwell must be 0..2000 ms in 100 ms increments');
 if(finite(r.bSpeedFraction,'B speed fraction')<0.01||r.bSpeedFraction>1)fail('B speed fraction must be 0.01..1');
 if(grid(r.workZ,0.05,'Work Z')<55||r.workZ>p.workZ)fail('Work Z must be 55..profile workZ on 0.05 grid');
 return r;
}
function selected(refs,mode,p){
 if(!Array.isArray(refs)||!refs.length)fail('At least one resistor must be selected');var seen={};refs.forEach(function(ref){if(typeof ref!=='string'||seen[ref]||!p.pads[ref])fail('Selected reference missing/duplicate in registered job: '+ref);seen[ref]=true;});
 return refs;
}
function plan(refs,r,p,currentRaw,usedGross,pendingAtStart){
 if(p.heightCalibrationPending===true)fail('New height calibration required');selected(refs,r.padMode,p);recipe(r,p);axisObject(currentRaw,'currentRaw');finite(usedGross,'used gross B');
 var stages=[],gross=0,current={X:currentRaw.X,Y:currentRaw.Y,Z:currentRaw.Z,A:currentRaw.A,B:currentRaw.B},pendingRetract=finite(pendingAtStart||0,'pending inter-resistor retract');if(pendingRetract>15)fail('Large relief: purge/re-prime over scrap before dispensing');
 function add(axis,value,speed,tag,dwell){if(axis==='X'||axis==='Y'){while(Math.abs(value-current[axis])>10.000001){add(axis,Math.round((current[axis]+(value>current[axis]?10:-10))*100)/100,speed,tag,0);}}var delta=value-current[axis];if(Math.abs(delta)<0.0001)return;if(axis==='B'){gross+=Math.abs(delta);}stages.push({axis:axis,target:value,speedFraction:speed,tag:tag||'',dwellMilliseconds:dwell||0});current[axis]=value;}
 function zPath(target){var mids=[];if((current.Z-p.travelZ)*(target-p.travelZ)<0)mids.push(p.travelZ);mids.push(target);mids.forEach(function(dest){while(Math.abs(dest-current.Z)>5){add('Z',current.Z+(dest>current.Z?5:-5),1,'z-transit');}add('Z',dest,1,'z-transit');});}
 refs.forEach(function(ref){var first=r.padMode==='2'?'2':'1',last=r.padMode==='1'?'1':'2',items=first===last?[first]:['1','2'];
  items.forEach(function(k){var t=p.pads[ref][k],work=r.workZ;if(p.vacuumReference&&typeof t.touchRawZ!=='number')fail('Explicit operator needle touch zero required');if(r.heightMode==='gap'){finite(t.touchRawZ,'Measured needle touch reference '+ref+'.'+k);work=Math.round((t.touchRawZ-r.gapMm)*100)/100;}if(work<p.rawBounds.Z.min-1e-8||work>p.rawBounds.Z.max+1e-8)fail('Pad work Z outside explicit raw bounds');var gap=typeof t.touchRawZ==='number'?t.touchRawZ-work:t.gapAtWorkZ+(p.workZ-work);if(gap-(typeof t.touchRawZ==='number'?0:p.gapUncertaintyMm)<0.1-1e-9)fail('Requested work Z violates 0.10 mm gap at '+ref+'.'+k);if(current.Z!==p.safeZ){zPath(p.safeZ);}add('X',t.tipXY[0],1,'registered-pad-xy');add('Y',t.tipXY[1],1,'registered-pad-xy');zPath(work);if(pendingRetract){add('B',Math.round((current.B-pendingRetract)*100)/100,r.bSpeedFraction,'restore-prior-inter-resistor-retract',0);pendingRetract=0;}add('B',Math.round((current.B-r.doseDegrees)*100)/100,r.bSpeedFraction,'dose',r.dwellMs);});
  var retract=r.doseDegrees*r.retractPercent/100;if(retract){var reliefTarget=Math.round((current.B+retract)*100)/100;pendingRetract=Math.round((reliefTarget-current.B)*100)/100;add('B',reliefTarget,r.bSpeedFraction,'inter-resistor-retract',r.retractDwellMs);}zPath(p.safeZ);
 });
 if(usedGross+gross>p.rodBudget.maximumAdditionalGrossDegrees)fail('Operator-session conservative rod-exposure planning budget exhausted');
 return {stages:stages,grossDegrees:gross,startB:currentRaw.B,endB:current.B,finalRaw:current,pendingRetractDegrees:pendingRetract};
}
function center(p,ref){if(!p.pads[ref])fail('Unknown resistor');var q=p.pads[ref];return [(q['1'].cameraXY[0]+q['2'].cameraXY[0])/2,(q['1'].cameraXY[1]+q['2'].cameraXY[1])/2];}
function plane(points,values){
 if(points.length!==3||values.length!==3)fail('Exactly three separated measurements required');
 var x=points[1][0]-points[0][0],y=points[1][1]-points[0][1],u=points[2][0]-points[0][0],v=points[2][1]-points[0][1],det=x*v-y*u;
 if(Math.abs(det)<25)fail('Calibration references too close or collinear (area must exceed 12.5 mm2)');
 values.forEach(function(n){finite(n,'measurement');});
 var a=((values[1]-values[0])*v-(values[2]-values[0])*y)/det,b=(x*(values[2]-values[0])-u*(values[1]-values[0]))/det;
 return [a,b,values[0]-a*points[0][0]-b*points[0][1]];
}
function evaluate(c,p){return c[0]*p[0]+c[1]*p[1]+c[2];}
function captures(samples,p){if(!Array.isArray(samples)||samples.length!==3)fail('Capture three distinct resistor references');var seen={};return samples.map(function(s){if(!s||seen[s.ref]||!p.pads[s.ref])fail('Distinct known references required');seen[s.ref]=true;return center(p,s.ref);});}
function alignment(samples,p){
 var pts=captures(samples,p),x=plane(pts,samples.map(function(s){return finite(s.cameraXY[0],'camera X');})),y=plane(pts,samples.map(function(s){return finite(s.cameraXY[1],'camera Y');}));
 var sx=Math.sqrt(x[0]*x[0]+y[0]*y[0]),sy=Math.sqrt(x[1]*x[1]+y[1]*y[1]),shear=x[0]*x[1]+y[0]*y[1],det=x[0]*y[1]-x[1]*y[0];
 if(Math.abs(sx-1)>.02||Math.abs(sy-1)>.02||Math.abs(shear)>.02||det<=0)fail('Alignment scale/shear/reflection exceeds 2% bounds');
 var out=JSON.parse(JSON.stringify(p));Object.keys(p.pads).forEach(function(ref){['1','2'].forEach(function(k){var old=p.pads[ref][k],q=out.pads[ref][k],nx=evaluate(x,old.cameraXY),ny=evaluate(y,old.cameraXY),dx=nx-old.cameraXY[0],dy=ny-old.cameraXY[1];if(Math.sqrt(dx*dx+dy*dy)>10)fail('Board shift exceeds 10 mm calibration envelope');q.cameraXY=[Math.round(nx*100)/100,Math.round(ny*100)/100];q.tipXY=[Math.round((old.tipXY[0]+dx)*100)/100,Math.round((old.tipXY[1]+dy)*100)/100];[q.cameraXY,q.tipXY].forEach(function(t){if(t[0]<p.rawBounds.X.min||t[0]>p.rawBounds.X.max||t[1]<p.rawBounds.Y.min||t[1]>p.rawBounds.Y.max)fail('Aligned pad exceeds existing raw bounds');});});});
 return {profile:out,transform:{x:x,y:y},fitNote:'Three-point exact affine fit; no independent residual check'};
}
function surface(samples,p){
 captures(samples,p);var pts=samples.map(function(s){if(['1','2'].indexOf(String(s.pad))<0)fail('Z capture requires pad');return p.pads[s.ref][String(s.pad)].tipXY;}),values=samples.map(function(s){finite(s.rawZ,'captured raw Z');finite(s.measuredGap,'measured gap');if(s.rawZ<55||s.rawZ>(p.calibrationRawZMax===undefined?p.workZ:p.calibrationRawZMax)+1e-8||s.measuredGap<.1||s.measuredGap>3)fail('Z measurement outside 55..workZ or 0.1..3 mm measured gap');return s.measuredGap+s.rawZ-p.workZ;}),c=plane(pts,values);
 if(Math.sqrt(c[0]*c[0]+c[1]*c[1])>.05)fail('Measured board slope exceeds 0.05 mm/mm');
 var out=JSON.parse(JSON.stringify(p));delete out.heightCalibrationPending;delete out.vacuumReference;delete out.needleTouchCalibrated;out.gapUncertaintyMm=Math.max(.3,p.gapUncertaintyMm);var minimum=Infinity;Object.keys(out.pads).forEach(function(ref){['1','2'].forEach(function(k){minimum=Math.min(minimum,evaluate(c,out.pads[ref][k].tipXY));});});var lift=Math.max(0,Math.ceil((out.gapUncertaintyMm+.1-minimum-1e-9)/.05)*.05);out.workZ=Math.round((p.workZ-lift)*100)/100;if(out.workZ<55)fail('Measured plane requires workZ below supported 55 mm range');c[2]+=p.workZ-out.workZ;Object.keys(out.pads).forEach(function(ref){['1','2'].forEach(function(k){var q=out.pads[ref][k];delete q.touchRawZ;q.gapAtWorkZ=evaluate(c,q.tipXY);if(q.gapAtWorkZ-out.gapUncertaintyMm<.1-1e-9||q.gapAtWorkZ>3)fail('Measured plane fails conservative gap bound at '+ref+'.'+k);});});return {profile:out,plane:c};
}
function needleTouch(p,reference,measurement){
 if(!reference||!reference.plane||!measurement)fail('Vacuum relative plane and explicit needle touch reference required');
 var xy;if(measurement.cameraXY!==undefined){if(!Array.isArray(measurement.cameraXY)||measurement.cameraXY.length!==2||measurement.operatorConfirmedBarelyTouching!==true)fail('Arbitrary needle touch requires explicit operator confirmation and camera XY');xy=measurement.cameraXY;finite(xy[0],'Needle touch camera X');finite(xy[1],'Needle touch camera Y');if(xy[0]<p.rawBounds.X.min||xy[0]>p.rawBounds.X.max||xy[1]<p.rawBounds.Y.min||xy[1]>p.rawBounds.Y.max)fail('Needle touch camera XY outside profile bounds');}else{if(!p.pads[measurement.ref]||['1','2'].indexOf(String(measurement.pad))<0)fail('Known pad or explicit arbitrary camera XY required');xy=p.pads[measurement.ref][String(measurement.pad)].cameraXY;}
 var c=reference.plane;['a','b','c'].forEach(function(k){finite(c[k],'Relative onset plane '+k);});finite(measurement.rawZ,'Needle touch raw Z');if(measurement.rawZ<p.rawBounds.Z.min-1e-8||measurement.rawZ>p.rawBounds.Z.max+1e-8)fail('Needle touch outside explicit Z bounds');
 var onset=c.a*xy[0]+c.b*xy[1]+c.c,out=JSON.parse(JSON.stringify(p));
 Object.keys(out.pads).forEach(function(ref){['1','2'].forEach(function(k){var t=out.pads[ref][k],o=c.a*t.cameraXY[0]+c.b*t.cameraXY[1]+c.c;t.touchRawZ=measurement.rawZ-(o-onset);t.gapAtWorkZ=t.touchRawZ-out.workZ;});});return out;
}
function fitNeedleTouches(samples,p){
 captures(samples,p);var points=samples.map(function(s){if(['1','2'].indexOf(String(s.pad))<0||s.operatorConfirmedBarelyTouching!==true)fail('Explicit bare-needle touch confirmation required at each pad');return p.pads[s.ref][String(s.pad)].tipXY;}),zs=samples.map(function(s){finite(s.rawZ,'Confirmed needle touch Z');if(s.rawZ<55||s.rawZ>63+1e-8||s.rawZ>p.rawBounds.Z.max+1e-8)fail('Needle touch must lie in reviewed 55..63 mm bounds');return s.rawZ;}),c=plane(points,zs);
 if(Math.sqrt(c[0]*c[0]+c[1]*c[1])>.05)fail('Needle touch plane slope exceeds 0.05 mm/mm');var out=JSON.parse(JSON.stringify(p));delete out.vacuumReference;delete out.heightCalibrationPending;out.needleTouchCalibrated=true;
 Object.keys(out.pads).forEach(function(ref){['1','2'].forEach(function(k){var t=out.pads[ref][k];t.touchRawZ=evaluate(c,t.tipXY);if(!isFinite(t.touchRawZ)||t.touchRawZ<55)fail('Invalid extrapolated touch height');t.gapAtWorkZ=t.touchRawZ-out.workZ;});});return {profile:out,plane:c};
}
function purgePlan(degrees,speed,p,raw,used){
 finite(degrees,'Purge degrees');finite(speed,'Purge speed');axisObject(raw,'Purge start');finite(used,'Used gross budget');if(degrees<1||degrees>1000||Math.abs(degrees-Math.round(degrees))>1e-8||speed<.01||speed>1)fail('Purge must be 1..1000 whole degrees, speed .01..1');
 var stages=[],b=raw.B,left=degrees,gross=0;while(left>0){var dose=Math.min(30,left),target=Math.round((b-dose)*100)/100;if(target<p.rawBounds.B.min||target>p.rawBounds.B.max)fail('Purge B target outside explicit profile bounds');var actual=Math.abs(target-b);stages.push({axis:'B',target:target,speedFraction:speed,grossDegrees:actual});gross+=actual;b=target;left-=dose;}
 if(used+gross>p.rodBudget.maximumAdditionalGrossDegrees)fail('Purge exceeds remaining gross travel budget');return {stages:stages,grossDegrees:gross,endB:b};
}
function pendingFromVerifiedStages(initial,stages){var pending=finite(initial,'Initial pending relief');stages.forEach(function(s){if(s.axis!=='B'||s.verified!==true)return;var delta=finite(s.reportedRaw.B,'Verified B')-finite(s.startRaw.B,'Starting B');if(delta>0){if(s.tag!=='inter-resistor-retract')fail('Unexpected positive B in dispense record');pending+=delta;}else pending=Math.max(0,pending+delta);});return Math.round(pending*100000000)/100000000;}
function reliefPlan(degrees,speed,p,raw,used,pending){
 finite(degrees,'Relief degrees');finite(speed,'Relief speed');finite(pending,'Manual relief');axisObject(raw,'Relief start');finite(used,'Used gross budget');if(degrees<1||degrees>300||Math.abs(degrees-Math.round(degrees))>1e-8||speed<.01||speed>1||pending<0)fail('Pressure relief must be 1..300 whole degrees, speed .01..1');
 var stages=[],b=raw.B,left=degrees,gross=0;while(left>0){var amount=Math.min(15,left),target=Math.round((b+amount)*100)/100,actual=target-b;if(target<p.rawBounds.B.min||target>p.rawBounds.B.max)fail('Relief B target outside explicit profile bounds');stages.push({axis:'B',target:target,speedFraction:speed,grossDegrees:actual});gross+=actual;b=target;left-=amount;}if(used+gross>p.rodBudget.maximumAdditionalGrossDegrees||pending+gross>p.rodBudget.maximumAdditionalGrossDegrees)fail('Relief exceeds remaining gross travel budget');return {stages:stages,grossDegrees:gross,endB:b};
}
function rodCapacity(budget,evidence){
 if(!budget||!evidence)fail('Gross budget and hash-bound rod evidence required');var degrees=finite(budget.maximumAdditionalGrossDegrees,'Gross-degree ceiling'),remaining=finite(evidence.planningRemainingMm,'Conservative remaining rod travel'),perDegree=finite(evidence.mmPerMotorDegreeNominal,'Nominal travel per motor degree');if(degrees<1||degrees>20000||remaining<0||perDegree<=0||degrees*perDegree>remaining)fail('Gross budget exceeds conservative rod travel capacity');return {grossDegrees:degrees,plannedTravelMm:degrees*perDegree,remainingPlanningMm:remaining};
}
function manualHandoff(current,expectedB){
 if(!current)fail('Manual handoff snapshot required');axisObject(current.raw,'Manual raw');axisObject(current.driver,'Manual driver');finite(expectedB,'Retained ledger B');Object.keys(current.raw).forEach(function(k){if(Math.abs(current.raw[k]-current.driver[k])>.005001)fail('Manual raw/driver mismatch '+k);});if(Math.abs(current.raw.B-expectedB)>.005001)fail('Manual B changed: preserve dose budget and reconcile before arming');return current;
}
var api={validateProfile:profile,validateRecipe:recipe,select: selected,plan:plan,center:center,fitAlignment:alignment,fitSurface:surface,applyNeedleTouch:needleTouch,validateManualHandoff:manualHandoff,fitNeedleTouches:fitNeedleTouches,validateRodCapacity:rodCapacity,planPurge:purgePlan,planRelief:reliefPlan,pendingFromVerifiedStages:pendingFromVerifiedStages};root.PasteOperatorPolicy=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(this);
