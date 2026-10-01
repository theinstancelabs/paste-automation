'use strict';
// Explicit one-attempt aspiration trial on a reviewed existing FTP paste defect.
(function(root){
function fail(s){throw Error(s);}
function scope(preview){return 'contiguous-native-ftp-one-pad-cleanup'+(preview?'-preview':'');}
function isCleanup(q){return !!q&&(q.scope===scope(false)||q.scope===scope(true));}
function ev(e){if(!e||typeof e.path!=='string'||e.path.charAt(0)!=='/'||!/^[a-f0-9]{64}$/.test(e.sha256))fail('Cleanup evidence path/hash required');return e;}
function finite(v){return typeof v==='number'&&isFinite(v);}
function validate(q,now){
 var t=q.ftpTargetRecord,c=t&&t.cleanupSequence;if(now===undefined)now=q.createdMs;
 if(!isCleanup(q)||q.mode!=='wet'||!t||t.scope!=='ftp-one-pad-cleanup-targets'||t.compensatedSequence!==undefined||t.inlineConditioning!==undefined||!c||c.schema!==1||c.protocol!=='positive-B-aspiration-lift-one-pad'||[6,20].indexOf(c.retractDegrees)<0||!finite(c.dwellMilliseconds)||Math.floor(c.dwellMilliseconds)!==c.dwellMilliseconds||c.dwellMilliseconds<0||c.dwellMilliseconds>2000)fail('Explicit bounded positive-B cleanup protocol required');
 if(!Array.isArray(t.pads)||t.pads.length!==1)fail('Cleanup requires exactly one reviewed defect pad');var p=t.pads[0];
 if(['R1.1','R40.1'].indexOf(p.padId)<0||p.padIdentityReviewed!==true||p.defectReviewed!==true)fail('Only explicitly reviewed R1.1 or R40.1 defect is in cleanup scope');ev(p.defectReportEvidence);ev(p.defectImageEvidence);
 if(!finite(p.defectCapturedMs)||Math.floor(p.defectCapturedMs)!==p.defectCapturedMs||!finite(now)||p.defectCapturedMs>t.reviewedMs||p.defectCapturedMs>now||now-p.defectCapturedMs>300000)fail('Fresh defect image before authored cleanup review required');return t;
}
function coverage(q,t){
 var p=t.pads[0],c=t.cleanupSequence,stages=q.previewStages,i=p.aspirationStageIndex,l=p.liftStageIndex;
 if(!finite(i)||Math.floor(i)!==i||i<0||l!==i+1||l!==stages.length-1||p.doseStageIndex!==undefined||p.doseStageIndices!==undefined)fail('One positive B followed immediately by final clearance lift required');
 var s=stages[i],lift=stages[l];if(!s||s.axis!=='B'||s.targetRaw.B-s.startRaw.B!==c.retractDegrees||(s.dwellMilliseconds||0)!==c.dwellMilliseconds||!lift||lift.axis!=='Z'||lift.startRaw.Z!==t.surface.rawZ||lift.targetRaw.Z!==q.xyClearanceRawZ)fail('Cleanup aspiration/dwell/lift differs');
 ['X','Y','Z','A'].forEach(function(k){if(s.startRaw[k]!==p.rawPose[k]||s.targetRaw[k]!==p.rawPose[k])fail('Cleanup B must stay at exact registered reviewed pad pose');});
 if(!s.gapEvidence||s.gapEvidence.path!==t.surfaceEvidence.path||s.gapEvidence.sha256!==t.surfaceEvidence.sha256||s.estimatedGapMm!==t.surface.estimatedGapMm||s.gapUncertaintyMm!==t.surface.gapUncertaintyMm)fail('Cleanup must retain exact above-board surface gap evidence');
 stages.forEach(function(v,n){if(v.axis==='B'&&n!==i)fail('Cleanup permits exactly one positive B, no forward extrusion or additional relief');});var covered={};covered[i]=true;return covered;
}
function verifyImage(q,read){var t=validate(q),p=t.pads[0],e=ev(p.defectReportEvidence),r=read(e,true),im=ev(p.defectImageEvidence),top=r&&r.afterImages&&r.afterImages.top;
 if(!r||r.controllerPositionVerified!==true||r.uncertainCompletion!==false||['completed-camera-survey-awaiting-image-review','completed-contiguous-air-batch-awaiting-observation'].indexOf(r.status)<0||!r.request||r.request.jvmStartMs!==q.jvmStartMs||r.request.liveConfigurationSha256!==q.liveConfigurationSha256||Date.parse(r.finishedAt)!==p.defectCapturedMs||!top||im.path!==e.path.slice(0,e.path.lastIndexOf('/')+1)+top.path)fail('Defect image must bind a fresh same-session verified camera report');read(im,false);
}
var api={scope:scope,isCleanup:isCleanup,validate:validate,coverage:coverage,verifyImage:verifyImage};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.PasteFtpOnePadCleanup=api;
})(this);
