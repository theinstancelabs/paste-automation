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
 if(p.safeZ!==32.25||p.travelZ!==53.45||typeof p.workZ!=='number'||p.workZ<55||p.workZ>58.2)fail('Reviewed 32.25/53.45/55..58.20 Z profile required');
 finite(p.gapUncertaintyMm,'gapUncertaintyMm');if(p.gapUncertaintyMm<0)fail('Nonnegative surface uncertainty required');
 if(!p.rawBounds||!p.headClearanceBounds||!p.pads||!Array.isArray(p.sourceEvidence)||!p.sourceEvidence.length)fail('Raw/head bounds, job pad table and source hashes required');
 axisObject(p.expectedRaw,'expectedRaw');axisObject(p.expectedDriver,'expectedDriver');
 if(!p.expectedNativePoses||Object.keys(p.expectedNativePoses).sort().join(',')!=='N1,N2,bottom,top')fail('Expected native head/camera poses required');
 ['N1','N2','top','bottom'].forEach(function(h){['x','y','z','rotation'].forEach(function(k){finite(p.expectedNativePoses[h][k],h+'.'+k);});});
 if(Math.abs(p.expectedRaw.Z-p.safeZ)>0.0001)fail('Profile must be captured at both-head safe Z');
 ['X','Y','Z','A','B'].forEach(function(a){var b=p.rawBounds[a];if(!b||finite(b.min,'rawBounds.'+a+'.min')>finite(b.max,'rawBounds.'+a+'.max'))fail('Ordered raw bounds required: '+a);});
 ['N1','N2'].forEach(function(h){var b=p.headClearanceBounds[h];if(!b)fail('Both-head bounds missing '+h);['minX','maxX','minY','maxY','minZ','maxZ'].forEach(function(k){finite(b[k],h+'.'+k);});});
 var refs=Object.keys(p.pads);if(!refs.length)fail('Registered resistor pad map required');
 refs.forEach(function(ref){if(!/^R(?:[1-9]|[1-3][0-9]|40)$/.test(ref))fail('Only resistor references R1..R40 accepted');['1','2'].forEach(function(k){var t=p.pads[ref][k];if(!t||!Array.isArray(t.cameraXY)||t.cameraXY.length!==2||!Array.isArray(t.tipXY)||t.tipXY.length!==2)fail('Camera/tip XY arrays required for '+ref+'.'+k);finite(t.cameraXY[0],ref+'.'+k+'.cameraXY.X');finite(t.cameraXY[1],ref+'.'+k+'.cameraXY.Y');finite(t.tipXY[0],ref+'.'+k+'.tipXY.X');finite(t.tipXY[1],ref+'.'+k+'.tipXY.Y');finite(t.gapAtWorkZ,ref+'.'+k+'.gapAtWorkZ');if(t.gapAtWorkZ-p.gapUncertaintyMm<0.1)fail('Current work-Z gap lower bound is below 0.10 mm at '+ref+'.'+k);});});
 if(!p.rodBudget||finite(p.rodBudget.baselineGrossDegrees,'rod baseline gross')<0||finite(p.rodBudget.maximumAdditionalGrossDegrees,'rod additional budget')<1||p.rodBudget.maximumAdditionalGrossDegrees>1000||finite(p.rodBudget.baselineB,'rod baseline B')!==p.expectedRaw.B)fail('Hash-bound conservative 41 mm planning budget required');
 return p;
}
function recipe(r,p){
 if(!r||['both','1','2'].indexOf(r.padMode)<0)fail('Pad mode must be both, 1 or 2');
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
 selected(refs,r.padMode,p);recipe(r,p);axisObject(currentRaw,'currentRaw');finite(usedGross,'used gross B');
 var stages=[],gross=0,current={X:currentRaw.X,Y:currentRaw.Y,Z:currentRaw.Z,A:currentRaw.A,B:currentRaw.B},pendingRetract=finite(pendingAtStart||0,'pending inter-resistor retract');
 function add(axis,value,speed,tag,dwell){if(axis==='X'||axis==='Y'){while(Math.abs(value-current[axis])>10.000001){add(axis,Math.round((current[axis]+(value>current[axis]?10:-10))*100)/100,speed,tag,0);}}var delta=value-current[axis];if(Math.abs(delta)<0.0001)return;if(axis==='B'){gross+=Math.abs(delta);}stages.push({axis:axis,target:value,speedFraction:speed,tag:tag||'',dwellMilliseconds:dwell||0});current[axis]=value;}
 function zPath(target){var mids=[];if((current.Z-p.travelZ)*(target-p.travelZ)<0)mids.push(p.travelZ);mids.push(target);mids.forEach(function(dest){while(Math.abs(dest-current.Z)>5){add('Z',current.Z+(dest>current.Z?5:-5),1,'z-transit');}add('Z',dest,1,'z-transit');});}
 refs.forEach(function(ref){var first=r.padMode==='2'?'2':'1',last=r.padMode==='1'?'1':'2',items=first===last?[first]:['1','2'];
  items.forEach(function(k){var t=p.pads[ref][k],gap=t.gapAtWorkZ+(p.workZ-r.workZ);if(gap-p.gapUncertaintyMm<0.1)fail('Requested work Z violates 0.10 mm conservative gap at '+ref+'.'+k);if(current.Z!==p.safeZ){zPath(p.safeZ);}add('X',t.tipXY[0],1,'registered-pad-xy');add('Y',t.tipXY[1],1,'registered-pad-xy');zPath(r.workZ);if(pendingRetract){add('B',Math.round((current.B-pendingRetract)*100)/100,r.bSpeedFraction,'restore-prior-inter-resistor-retract',0);pendingRetract=0;}add('B',Math.round((current.B-r.doseDegrees)*100)/100,r.bSpeedFraction,'dose',r.dwellMs);});
  var retract=r.doseDegrees*r.retractPercent/100;if(retract){var reliefTarget=Math.round((current.B+retract)*100)/100;pendingRetract=Math.round((reliefTarget-current.B)*100)/100;add('B',reliefTarget,r.bSpeedFraction,'inter-resistor-retract',r.retractDwellMs);}zPath(p.safeZ);
 });
 if(usedGross+gross>p.rodBudget.maximumAdditionalGrossDegrees)fail('Operator-session conservative rod-exposure planning budget exhausted');
 return {stages:stages,grossDegrees:gross,startB:currentRaw.B,endB:current.B,finalRaw:current,pendingRetractDegrees:pendingRetract};
}
var api={validateProfile:profile,validateRecipe:recipe,select: selected,plan:plan};root.PasteOperatorPolicy=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(this);
