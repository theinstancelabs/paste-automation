'use strict';
// Pure, narrowly scoped FTP demo target policy. readEvidence is supplied by the
// caller and MUST verify file SHA-256 before returning JSON or image bytes.
(function(root){
var fail=function(s){throw Error(s);},hash=/^[a-f0-9]{64}$/;
var Group=typeof module!=='undefined'&&module.exports?require('./ftp-pad-group.cjs'):root.PasteFtpPadGroup;
var Revalidation=typeof module!=='undefined'&&module.exports?require('./ftp-registration-revalidation.cjs'):root.PasteFtpRegistrationRevalidation;
var Inline=typeof module!=='undefined'&&module.exports?require('./ftp-inline-conditioning.cjs'):root.PasteFtpInlineConditioning;
function number(v,label){if(typeof v!=='number'||!isFinite(v))fail(label+' must be finite');return v;}
function evidence(e){if(!e||typeof e.path!=='string'||e.path.charAt(0)!=='/'||!hash.test(e.sha256))fail('FTP evidence path/hash required');return e;}
function same(a,b){if(a===b)return true;if(!a||!b||typeof a!=='object'||typeof b!=='object'||Array.isArray(a)!==Array.isArray(b))return false;var ak=Object.keys(a).sort(),bk=Object.keys(b).sort();return JSON.stringify(ak)===JSON.stringify(bk)&&ak.every(function(k){return same(a[k],b[k]);});}
function close(a,b,label){if(Math.abs(number(a,label)-Math.round(number(b,label)*100)/100)>1e-9)fail(label+' differs from registered target');}
function scope(preview,q){if(Group&&Group.isGroup(q))return Group.scope(preview);return Inline&&Inline.isInline(q)?Inline.scope(preview):'contiguous-native-ftp-two-pad'+(preview?'-preview':'');}
function isFtp(q){return q&&(q.scope===scope(false)||q.scope===scope(true)||Inline&&Inline.isInline(q));}
function integer(v,lo,hi,label){if(Math.floor(number(v,label))!==v||v<lo||v>hi)fail(label+' outside reviewed integer range');return v;}
function entryTime(q,now){if(Inline&&Inline.isInline(q))return;var c=q.ftpTargetRecord&&q.ftpTargetRecord.compensatedSequence;if(!c)return;var elapsed=number(now,'entry time')-number(c.conditioningFinishedMs,'conditioning finish');if(elapsed<0||elapsed>integer(c.maximumElapsedMilliseconds,1,300000,'conditioning elapsed limit'))fail('FTP conditioning entry state expired');}
function retractWait(c){var v=c.retractDwellMilliseconds===undefined?0:c.retractDwellMilliseconds;if([0,200,500].indexOf(v)<0)fail('FTP retraction wait must be 0, 200 or 500 ms');return v;}
function compensated(q,t,now){
 var c=t.compensatedSequence;if(c===undefined)return null;if(!c)fail('Explicit compensated FTP object required');
 if(q.mode!=='wet'||c.schema!==1||c.protocol!==(Group&&Group.isGroup(q)?'restore-dose-retract-lift-eight-pad':'restore-dose-retract-lift-two-pad')||[2,3,4,6,12,20].indexOf(c.doseDegrees)<0||[2,3,4,6].indexOf(c.retractDegrees)<0)fail('Unknown compensated FTP protocol/amount');
 integer(c.dwellMilliseconds,0,2000,'FTP dose dwell');entryTime(q,now);var wait=retractWait(c),idle=c.idleReliefDegrees===undefined?20:c.idleReliefDegrees;if([20,40].indexOf(idle)<0)fail('FTP idle relief must be 20 or 40 degrees');
 if(!Inline.isInline(q))['conditioningReportEvidence','conditioningLedgerEvidence','preparationExperimentEvidence','tipObservationEvidence'].forEach(function(k){evidence(c[k]);});
 if(!Inline.isInline(q)&&(!same(c.conditioningReportEvidence,q.previousReportEvidence)||c.conditioningLedgerEvidence.sha256!==q.previousLedgerSha256))fail('FTP conditioning must be exact preceding charged report/ledger');
 var covered=Inline.isInline(q)?Inline.prefix(q):{},last=Inline.isInline(q)?t.inlineConditioning.prefixStageCount-1:-1;
 function at(i,axis){integer(i,0,q.previewStages.length-1,'FTP stage index');var st=q.previewStages[i];if(st.axis!==axis||covered[i])fail('FTP stage axis/duplicate index');covered[i]=true;return st;}
 function b(i,delta,p,dwell){var st=at(i,'B');if(st.targetRaw.B-st.startRaw.B!==delta||(st.dwellMilliseconds||0)!==dwell)fail('FTP compensated amount/dwell differs');['X','Y','Z','A'].forEach(function(k){if(st.startRaw[k]!==p[k]||st.targetRaw[k]!==p[k])fail('FTP compensated pose differs');});var gap=t.surface.estimatedGapMm+(t.surface.rawZ-p.Z);if(!same(st.gapEvidence,t.surfaceEvidence)||Math.abs(number(st.estimatedGapMm,'derived gap')-gap)>1e-9||st.gapUncertaintyMm!==t.surface.gapUncertaintyMm)fail('FTP compensated gap differs');}
 t.pads.forEach(function(p){
  if(p.doseStageIndex!==undefined)fail('Compensated FTP uses explicit doseStageIndices only');
  var ds=p.doseStageIndices,count=c.doseDegrees===12?2:1;
  if(!Array.isArray(ds)||ds.length!==count||p.restoreStageIndex<=last)fail('FTP ordered dose group required');
  b(p.restoreStageIndex,-c.retractDegrees,p.rawPose,0);
  ds.forEach(function(i,n){if(i!==p.restoreStageIndex+1+n)fail('FTP dose stages must immediately follow restore');b(i,c.doseDegrees===12?-6:-c.doseDegrees,p.rawPose,n===count-1?c.dwellMilliseconds:0);});
  if(p.retractStageIndex!==ds[count-1]+1||p.liftStageIndex!==p.retractStageIndex+1)fail('FTP immediate retract and lift required');
  b(p.retractStageIndex,c.retractDegrees,p.rawPose,wait);var lift=at(p.liftStageIndex,'Z');if(lift.startRaw.Z!==t.surface.rawZ||lift.targetRaw.Z!==q.xyClearanceRawZ)fail('FTP lift must reach common clearance');last=p.liftStageIndex;
 });
 var idleIndices;if(idle===20){if(c.finalIdleStageIndices!==undefined)fail('Single idle uses finalIdleStageIndex');idleIndices=[c.finalIdleStageIndex];}else{if(c.finalIdleStageIndex!==undefined||!Array.isArray(c.finalIdleStageIndices)||c.finalIdleStageIndices.length!==2)fail('Double idle needs exactly two finalIdleStageIndices');idleIndices=c.finalIdleStageIndices;}
 idleIndices.forEach(function(i,n){if(i!==last+1+n||n===idleIndices.length-1&&i!==q.previewStages.length-1)fail('FTP final idle must immediately follow final pad lift and end route');var final=q.previewStages[i];if(!final)fail('FTP final idle stage missing');b(i,20,{X:final.startRaw.X,Y:final.startRaw.Y,Z:q.xyClearanceRawZ,A:q.expectedRaw.A},n===idleIndices.length-1?2000:0);});
 q.previewStages.forEach(function(st,i){if(st.axis==='B'&&!covered[i])fail('FTP unaccounted B stage');});return covered;
}
function verifyConditioning(q,read){if(Inline.isInline(q)){Inline.sources(q,read);return;}
 var t=q.ftpTargetRecord,c=t.compensatedSequence;if(!c)return;
 var wait=retractWait(c),r=read(c.conditioningReportEvidence,true),l=read(c.conditioningLedgerEvidence,true),e=read(c.preparationExperimentEvidence,true),o=read(c.tipObservationEvidence,true),rq=r&&r.request;
 if(!rq||r.status!=='completed-contiguous-batch-awaiting-observation'||r.controllerPositionVerified!==true||r.uncertainCompletion!==false||r.id!==rq.id||rq.scope!=='contiguous-native-scrap-batch'||rq.mode!=='wet'||rq.sessionId!==q.sessionId||rq.syringeId!==q.syringeId||rq.jvmStartMs!==q.jvmStartMs||rq.liveConfigurationSha256!==q.liveConfigurationSha256||r.completedLedgerSha256!==q.previousLedgerSha256)fail('Verified same-session scrap conditioning report required');
 if(!isFinite(Date.parse(r.finishedAt))||Date.parse(r.finishedAt)<c.conditioningFinishedMs||!l||l.status!=='verified'||l.sessionId!==q.sessionId||l.syringeId!==q.syringeId||l.lastVerifiedB!==q.expectedRaw.B||!r.afterQuerySnapshot||r.afterQuerySnapshot.raw.B!==q.expectedRaw.B)fail('FTP conditioning terminal B/ledger/time differs');
 if(!e||e.schema!==1||e.scope!=='reviewed-scrap-retraction-coupon'||e.mode!=='transfer-preparation'||e.retractDegrees!==c.retractDegrees||e.maximumTransferElapsedMilliseconds!==c.maximumElapsedMilliseconds||e.conditioningDoseDegrees!==20||(e.retractDwellMilliseconds===undefined?0:e.retractDwellMilliseconds)!==wait)fail('Explicit transfer-preparation experiment required');
 var review=read(evidence(rq.clearanceReviewEvidence),true);if(!same(review.experimentEvidence,c.preparationExperimentEvidence))fail('Conditioning review does not bind preparation experiment');
 var stages=rq.previewStages,done=r.stages;if(!Array.isArray(stages)||stages.length<3||!Array.isArray(done)||done.length!==stages.length)fail('Complete conditioning stage history required');
 stages.forEach(function(s,i){var d=done[i];if(!d||d.index!==i||d.verified!==true||d.axis!==s.axis||!same(d.startRaw,s.startRaw)||!same(d.targetRaw,s.targetRaw))fail('Unverified conditioning stage');});
 var n=stages.length;if(Date.parse(done[n-2].finishedAt)!==c.conditioningFinishedMs)fail('Conditioning clock must start at verified retraction');var dose=stages[n-3],retract=stages[n-2],lift=stages[n-1];
 if(dose.axis!=='B'||dose.targetRaw.B-dose.startRaw.B!==-20||dose.startRaw.Z!==e.workRawZ||(dose.dwellMilliseconds||0)!==(e.conditioningDwellMilliseconds===undefined?(e.dwellMilliseconds===undefined?2000:e.dwellMilliseconds):e.conditioningDwellMilliseconds)||retract.axis!=='B'||retract.targetRaw.B-retract.startRaw.B!==c.retractDegrees||(retract.dwellMilliseconds||0)!==wait||lift.axis!=='Z'||lift.targetRaw.Z!==e.clearanceRawZ||!same(dose.targetRaw,retract.startRaw)||!same(retract.targetRaw,lift.startRaw)||!same(lift.targetRaw,rq.finalTargetRaw)||!same(lift.targetRaw,r.afterQuerySnapshot.raw)||lift.targetRaw.B!==q.expectedRaw.B)fail('Conditioning must end with dose, selected retract, lift and no idle relief');
 if(wait){var w=done[n-2].dwell;if(!w||w.requestedMilliseconds!==wait||w.stopObserved!==false||number(w.actualElapsedMilliseconds,'actual conditioning retract wait')<wait||!isFinite(Date.parse(w.endedAt))||Date.parse(w.endedAt)<c.conditioningFinishedMs+wait||Date.parse(w.endedAt)>Date.parse(r.finishedAt)||!o||number(o.capturedMs,'post-wait tip capture')<Date.parse(r.finishedAt))fail('Verified conditioning retract dwell and subsequent tip observation required');}
 var tail=l.entries&&l.entries[l.entries.length-1];if(!tail||tail.status!=='verified'||tail.batchId!==r.id||tail.stageIndex!==n-2||tail.targetB!==q.expectedRaw.B||tail.deltaDegrees!==c.retractDegrees)fail('Conditioning is not the current charged ledger tail');
 if(!o||o.noLongStrand!==true||typeof o.reviewedBy!=='string'||!o.reviewedBy.trim()||!same(o.conditioningReportEvidence,c.conditioningReportEvidence)||integer(o.reviewedMs,c.conditioningFinishedMs,t.reviewedMs,'tip observation time')!==o.reviewedMs||integer(o.capturedMs,c.conditioningFinishedMs,o.reviewedMs,'tip capture time')!==o.capturedMs)fail('Fresh authored tip observation required');read(evidence(o.imageEvidence),false);
}
function validate(q,now){
 var group=Group&&Group.isGroup(q);if(group)Group.validate(q,now);var t=q.ftpTargetRecord;if(!Inline.isInline(q)&&t&&t.inlineConditioning!==undefined)fail('Inline conditioning requires its separate scope');if(!t||t.schema!==1||t.scope!==(group?'ftp-eight-pad-commissioning-targets':'ftp-two-pad-commissioning-targets')||typeof t.boardId!=='string'||!t.boardId.trim())fail('Explicit FTP board identity/target record required');
 evidence(q.ftpTargetEvidence);if(t.quantizationMm!==0.01)fail('FTP targets must explicitly use the 0.01 mm report grid');
 if(t.sessionId!==q.sessionId||t.jvmStartMs!==q.jvmStartMs||t.liveConfigurationSha256!==q.liveConfigurationSha256)fail('FTP session/configuration mismatch');
 if(typeof t.reviewedBy!=='string'||!t.reviewedBy.trim()||Math.floor(number(t.reviewedMs,'FTP review time'))!==t.reviewedMs||t.reviewedMs>now||now-t.reviewedMs>300000)fail('Fresh explicitly authored FTP review required');
 if(t.boardCleaned!==true||t.padsAvailable!==true||t.boardUnmovedSinceRegistration!==true||t.provenance!=='commissioning-provisional'||t.precisionCalibrated!==false||t.flowCalibrated!==false)fail('Explicit cleaned/unmoved/available FTP attestations and provisional status required');
 evidence(t.cadEvidence);evidence(t.registrationEvidence);evidence(t.tipOffsetEvidence);evidence(t.surfaceEvidence);evidence(t.padAvailabilityImage);
 if(!Array.isArray(t.cameraMinusTipXYMm)||t.cameraMinusTipXYMm.length!==2)fail('Explicit parent-chosen provisional tip offset required');t.cameraMinusTipXYMm.forEach(function(x){number(x,'tip offset');});
 var s=t.surface;if(!s||number(s.rawZ,'FTP dispense Z')<=q.xyClearanceRawZ||number(s.estimatedGapMm,'FTP gap')<=0||number(s.gapUncertaintyMm,'FTP uncertainty')<0||s.estimatedGapMm-s.gapUncertaintyMm<0.1)fail('FTP board-specific positive gap required');
 if(!Array.isArray(t.padChecks)||t.padChecks.length!==3||t.padChecks.map(function(c){return c.reference;}).sort().join(',')!=='R1,R16,R40')fail('Three distant FTP pad checks required');
 t.padChecks.forEach(function(c){if(c.reviewedAligned!==true||!new RegExp('^'+c.reference+'\\.[12]$').test(c.padId))fail('Explicit reviewed distant-pad identity required');evidence(c.reportEvidence);evidence(c.imageEvidence);});
 if(!Array.isArray(t.pads)||t.pads.length!==(group?8:2))fail('Exactly two FTP pads required');
 var ids={},ref=null,indices={};t.pads.forEach(function(p){var m=/^(R(?:[1-9]|[1-3][0-9]|40))\.([12])$/.exec(p.padId);if(!m||ids[p.padId]||!group&&ref&&m[1]!==ref)fail('Two unique pads of the same resistor required');ids[p.padId]=true;ref=m[1];
  if(!p.rawPose)fail('FTP pad pose required');['X','Y','Z','A'].forEach(function(k){number(p.rawPose[k],'pad '+k);});
  if(['X','Y','Z'].some(function(k){return Math.abs(p.rawPose[k]-Math.round(p.rawPose[k]*100)/100)>1e-9;}))fail('FTP raw target must be on the 0.01 mm report grid');
  if(p.rawPose.Z!==s.rawZ||p.rawPose.A!==q.expectedRaw.A)fail('FTP target Z/A differs');
  if(q.mode==='wet'&&!t.compensatedSequence){var i=number(p.doseStageIndex,'dose stage');if(Math.floor(i)!==i||i<0||i>=q.previewStages.length||indices[i])fail('Unique FTP dose stage indices required');indices[i]=p;}
  else if(q.mode==='air'&&p.doseStageIndex!==null)fail('Air FTP record must not map a B dose stage');
 });
 if(q.rawBounds.Z.max>(Inline.isInline(q)?Math.max(s.rawZ,t.inlineConditioning.experiment.workRawZ):s.rawZ))fail('FTP route exceeds reviewed board dispense Z');
 var coverage=compensated(q,t,now);
 var doses=0;q.previewStages.forEach(function(st,i){if(Inline.isInline(q)&&i<t.inlineConditioning.prefixStageCount)return;if(st.wipeReview===true||((st.axis==='X'||st.axis==='Y')&&st.startRaw.Z!==q.xyClearanceRawZ))fail('FTP branch forbids low XY/wipe');
  if(coverage)return;
  if(st.axis==='B'&&st.targetRaw.B>=st.startRaw.B)fail('FTP permits only its two negative B dose stages');
  if(st.axis==='B'&&st.targetRaw.B<st.startRaw.B){var p=indices[i];if(!p)fail('Negative B outside the two FTP dose stages');['X','Y','Z','A'].forEach(function(k){if(st.startRaw[k]!==p.rawPose[k]||st.targetRaw[k]!==p.rawPose[k])fail('FTP dose pose differs from target record');});if(!same(st.gapEvidence,t.surfaceEvidence)||st.estimatedGapMm!==s.estimatedGapMm||st.gapUncertaintyMm!==s.gapUncertaintyMm)fail('FTP dose gap differs from board evidence');doses++;}
 });
 if(q.mode==='wet'&&!coverage&&doses!==2)fail('Exactly one negative B dose per FTP pad required');
 return t;
}
function affineSources(q,reg,registered,read,observe,fidReports,revalidated){
 if(!same(reg.fittedFiducials,['FID1','FID2','FID3'])||reg.independentFID3Check!==undefined)fail('Affine must identify three fitted fiducials and independent pads, not an independent FID3');
 function pair(v,label){if(!Array.isArray(v)||v.length!==2)fail(label+' pair required');return [number(v[0],label),number(v[1],label)];}
 function inverse(m){if(!Array.isArray(m)||m.length!==2)fail('2x2 matrix required');var a=pair(m[0],'matrix'),b=pair(m[1],'matrix'),d=a[0]*b[1]-a[1]*b[0];if(!isFinite(d)||Math.abs(d)<1e-9)fail('Degenerate matrix');return [[b[1]/d,-a[1]/d],[-b[0]/d,a[0]/d]];}
 function multiply(a,b){return [[a[0][0]*b[0][0]+a[0][1]*b[1][0],a[0][0]*b[0][1]+a[0][1]*b[1][1]],[a[1][0]*b[0][0]+a[1][1]*b[1][0],a[1][0]*b[0][1]+a[1][1]*b[1][1]]];}
 function distance(a,b){a=pair(a,'point');b=pair(b,'point');return Math.sqrt(Math.pow(a[0]-b[0],2)+Math.pow(a[1]-b[1],2));}
 function equalPair(a,b,label){if(distance(a,b)>1e-7)fail(label+' differs');}
 function frame(report){var snap=report.afterQuerySnapshot,raw=snap&&snap.raw,top=snap&&snap.nativePoses&&snap.nativePoses.top;if(!raw||!top||!same([raw.Z,raw.A,raw.B],reg.session.fixedRawZAB)||!same([top.z,top.rotation],reg.session.topCameraZRotation))fail('Affine camera proof Z/A/B or imaging plane differs');return pair([top.x,top.y],'camera center');}
 var tr=reg.transformFromThreeFiducials,m=tr&&tr.matrix,t=tr&&tr.translationMm;inverse(m);t=pair(t,'affine translation');var a=m[0][0],b=m[0][1],c=m[1][0],d=m[1][1],det=a*d-b*c,aa=a*a+c*c,bb=b*b+d*d,ab=a*b+c*d,disc=Math.sqrt(Math.pow(aa-bb,2)+4*ab*ab),lo=Math.sqrt(Math.max(0,(aa+bb-disc)/2)),hi=Math.sqrt(Math.max(0,(aa+bb+disc)/2)),skew=Math.abs(Math.acos(Math.max(-1,Math.min(1,ab/Math.sqrt(aa*bb))))*180/Math.PI-90);
 if(det<=0||number(lo,'affine minimum scale')<.99-1e-12||number(hi,'affine maximum scale')>1.01+1e-12||number(skew,'affine skew')>.3+1e-12)fail('Affine orientation/scale/skew gate failed');
 function apply(p){p=pair(p,'design point');return [a*p[0]+b*p[1]+t[0],c*p[0]+d*p[1]+t[1]];}
 var used={};['FID1','FID2','FID3'].forEach(function(k){var v=reg.measurements[k],report=fidReports[k],xy=frame(report);equalPair(v.measuredTopCameraXYMm,xy,'Fitted camera source');equalPair(apply(v.designXYMm),xy,'Affine fiducial fit');used[report.id]=true;});
 Object.keys(registered).forEach(function(k){equalPair(apply(registered[k].designXYMm),registered[k].machineXYMm,'Affine pad prediction');});
 var je=evidence(reg.imageJacobianEvidence),j=read(je,true),samples=j&&j.sourceMeasurements;
 if(!j||j.schema!==1||j.scope!=='measured-top-camera-image-jacobian'||!same(j.session,{jvmStartMs:q.jvmStartMs,liveConfigurationSha256:q.liveConfigurationSha256})||!same(j.fixedRawZAB,reg.session.fixedRawZAB)||typeof j.reviewedBy!=='string'||!j.reviewedBy.trim()||!isFinite(j.reviewedMs)||Math.floor(j.reviewedMs)!==j.reviewedMs||j.reviewedMs>q.ftpTargetRecord.reviewedMs||!revalidated&&q.ftpTargetRecord.reviewedMs-j.reviewedMs>3600000||!Array.isArray(samples)||samples.length!==3)fail('Reviewed measured same-session Jacobian required');
 var centers=[],positions=[],jids={};samples.forEach(function(v){var report=read(evidence(v.report),true);observe(report,v.report,evidence(v.image));if(jids[report.id]||Date.parse(report.finishedAt)>j.reviewedMs)fail('Jacobian source identity/review time differs');jids[report.id]=true;var xy=frame(report);equalPair(v.rawXY,[report.afterQuerySnapshot.raw.X,report.afterQuerySnapshot.raw.Y],'Jacobian raw pose');positions.push(xy);centers.push(pair(v.centerPixels,'Jacobian center'));});
 function displacement(ps){return [[ps[1][0]-ps[0][0],ps[2][0]-ps[0][0]],[ps[1][1]-ps[0][1],ps[2][1]-ps[0][1]]];}
 var derived=multiply(displacement(centers),inverse(displacement(positions))),jm=j.pixelShiftPerCameraMm,inv=inverse(jm);equalPair(derived[0],jm[0],'Measured Jacobian');equalPair(derived[1],jm[1],'Measured Jacobian');
 var checks=reg.independentHeldOutPadChecks;if(!Array.isArray(checks)||checks.length!==3||checks.map(function(v){return v.padId;}).sort().join(',')!=='R1.2,R16.1,R40.1')fail('Three independent affine pad checks required');
 checks.forEach(function(v){if(v.padIdentityReviewed!==true||v.centerMeasurementReviewed!==true)fail('Explicit independent pad image review required');var report=read(evidence(v.report),true);observe(report,v.report,evidence(v.image));if(used[report.id])fail('Pad checks must be independent of fitted fiducials and each other');used[report.id]=true;var xy=frame(report),size=pair(v.imageSizePixels,'image size'),p=pair(v.observedCenterPixel,'observed pad center');if(size.some(function(n){return n<2||Math.floor(n)!==n;})||p.some(function(n,i){return n<0||n>=size[i];}))fail('Pad image bounds invalid');var center=[(size[0]-1)/2,(size[1]-1)/2],delta=[p[0]-center[0],p[1]-center[1]],measured=[xy[0]-inv[0][0]*delta[0]-inv[0][1]*delta[1],xy[1]-inv[1][0]*delta[0]-inv[1][1]*delta[1]],px=distance(p,center),mm=distance(measured,registered[v.padId].machineXYMm);if(px>8||mm>.08)fail('Independent affine pad exceeds 8 pixels or 0.08 mm');equalPair(v.cameraXYMm,xy,'Pad camera source');equalPair(v.imageCenterPixel,center,'Pad image center');equalPair(v.measuredPadXYMm,measured,'Measured pad point');equalPair(v.predictedMachineXYMm,registered[v.padId].machineXYMm,'Pad prediction');if(Math.abs(number(v.imageCenterErrorPx,'pad pixels')-px)>1e-7||Math.abs(number(v.residualMm,'pad residual')-mm)>1e-7)fail('Independent pad residual metadata differs');var current=q.ftpTargetRecord.padChecks.filter(function(p){return p.padId===v.padId;})[0];if(!current||!same(current.reportEvidence,v.report)||!same(current.imageEvidence,v.image))fail('FTP target pad checks must bind the accepted affine held-out images');});
}
function verifySources(q,readEvidence){
 if(Group&&Group.isGroup(q))Group.verifyImages(q,readEvidence);
 var t=q.ftpTargetRecord,actual=readEvidence(evidence(q.ftpTargetEvidence),true);if(!same(actual,t))fail('FTP target record bytes/content differ');
 var reg=readEvidence(t.registrationEvidence,true);readEvidence(t.cadEvidence,false);readEvidence(t.padAvailabilityImage,false);
 var affine=reg&&reg.scope==='offline-fresh-ftp-three-fiducial-affine-with-held-out-pad-checks';if(!reg||!affine&&reg.scope!=='offline-fresh-ftp-two-fiducial-transform-with-third-point-check'||!reg.acceptance||reg.acceptance.passed!==true||!same(reg.board,t.cadEvidence)||!reg.session||reg.session.jvmStartMs!==q.jvmStartMs||reg.session.liveConfigurationSha256!==q.liveConfigurationSha256||!affine&&(!reg.independentFID3Check||number(reg.independentFID3Check.residualMm,'FID3 residual')<0||reg.independentFID3Check.residualMm>0.08))fail('Accepted same-session three-fiducial registration required');
 var revalidated=Revalidation.verify(q,reg,readEvidence);
 function observation(report,ev,image){
  if(!report||report.controllerPositionVerified!==true||report.uncertainCompletion!==false||['completed-camera-survey-awaiting-image-review','completed-contiguous-air-batch-awaiting-observation'].indexOf(report.status)<0||!report.request||report.request.jvmStartMs!==q.jvmStartMs||report.request.liveConfigurationSha256!==q.liveConfigurationSha256)fail('FTP camera evidence session/completion mismatch');
  var finished=Date.parse(report.finishedAt);if(!isFinite(finished)||finished>t.reviewedMs||!revalidated&&t.reviewedMs-finished>3600000)fail('FTP registration/pad checks must be reviewed within one hour');
  var top=report.afterImages&&report.afterImages.top;if(!top||image.path!==ev.path.slice(0,ev.path.lastIndexOf('/')+1)+top.path)fail('FTP image must belong to its camera report');readEvidence(image,false);
 }
 var fidReports={};['FID1','FID2','FID3'].forEach(function(k){var m=reg.measurements&&reg.measurements[k];if(!m||number(m.imageCenterErrorPx,'fiducial centering')<0||m.imageCenterErrorPx>2)fail('Reviewed three centered fiducials required');var report=readEvidence(evidence(m.report),true);observation(report,m.report,evidence(m.image));fidReports[k]=report;});
 var registered={};if(!Array.isArray(reg.resistorPadMachineXYTargets)||reg.resistorPadMachineXYTargets.length!==80)fail('FTP registration must contain 80 pad targets');reg.resistorPadMachineXYTargets.forEach(function(p){if(registered[p.padId])fail('Duplicate registered pad');registered[p.padId]=p;});
 t.padChecks.forEach(function(c){var report=readEvidence(c.reportEvidence,true);observation(report,c.reportEvidence,c.imageEvidence);var p=registered[c.padId],cam=report.afterQuerySnapshot&&report.afterQuerySnapshot.nativePoses&&report.afterQuerySnapshot.nativePoses.top;if(!p||!cam||Math.sqrt(Math.pow(number(cam.x,'check camera X')-number(p.machineXYMm[0],'registered X'),2)+Math.pow(number(cam.y,'check camera Y')-number(p.machineXYMm[1],'registered Y'),2))>0.1)fail('Distant-pad camera location differs from registration');});
 if(affine)affineSources(q,reg,registered,readEvidence,observation,fidReports,revalidated);
 var off=readEvidence(t.tipOffsetEvidence,true),surf=readEvidence(t.surfaceEvidence,true);
 [off,surf].forEach(function(v){if(!v||v.boardId!==t.boardId||v.provenance!=='commissioning-provisional'||v.precisionCalibrated!==false||v.jvmStartMs!==q.jvmStartMs||v.liveConfigurationSha256!==q.liveConfigurationSha256||typeof v.reviewedBy!=='string'||!v.reviewedBy.trim())fail('Explicit provisional board/tip evidence required');});
 readEvidence(evidence(off.basisEvidence),false);readEvidence(evidence(surf.basisEvidence),false);
 if(!same(off.cameraMinusTipXYMm,t.cameraMinusTipXYMm)||!same(surf.surface,t.surface))fail('Selected tip offset or Z/gap differs from authored evidence');
 t.pads.forEach(function(p){var rp=registered[p.padId];if(!rp)fail('FTP pad missing from registration');close(p.rawPose.X,rp.machineXYMm[0]-t.cameraMinusTipXYMm[0],'registered head X');close(p.rawPose.Y,rp.machineXYMm[1]-t.cameraMinusTipXYMm[1],'registered head Y');});
 verifyConditioning(q,readEvidence);
 return t;
}
var api={entryTime:entryTime,scope:scope,isFtp:isFtp,validate:validate,verifySources:verifySources,same:same};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.PasteFtpTwoPad=api;
})(this);
