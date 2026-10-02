// One owned native task for a bounded contiguous scrap air or wet batch.
// Parent-reviewed signed commissioning action; exact detached preview required per request.
var PASTE_CONTIGUOUS_BATCH_ENABLED = true;
// No serial ownership changes, A move, wrap/reset, pickup, vacuum or current change.
// Uses the existing single-worker native executor with audited busy bookkeeping;
// bypasses the public wrapper whose completion/exception cleanup can flush motion.
(function(){
 if(!PASTE_CONTIGUOUS_BATCH_ENABLED)throw Error("Commissioning stroke disabled pending independent source, test and native-preview review");
 var C=Java.type('org.openpnp.model.Configuration'),F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8,
 MD=Java.type('java.security.MessageDigest'),MM=Java.type('org.openpnp.model.LengthUnit').Millimeters,AL=Java.type('org.openpnp.model.AxesLocation'),
 MO=Java.type('org.openpnp.model.Motion$MotionOption'),CT=Java.type('org.openpnp.machine.reference.driver.GcodeDriver$CommandType'),I=Java.type('javax.imageio.ImageIO');
 var root='/home/lumen/lumenpnp/',m=C.get().getMachine(),planner=m.getMotionPlanner();
 function uiStatus(text){
  try{Java.type('javax.swing.SwingUtilities').invokeLater(new (Java.type('java.lang.Runnable'))({run:function(){try{Java.type('org.openpnp.gui.MainFrame').get().setStatus(String(text));}catch(e){java.lang.System.err.println('Paste status update skipped: '+e);}}}));}
  catch(e){try{java.lang.System.err.println('Paste status update skipped: '+e);}catch(ignore){}}
 }
 function read(p){return String(new java.lang.String(Fs.readAllBytes(new F(p).toPath()),UTF));}
 function hash(bytes){var a=MD.getInstance('SHA-256').digest(bytes),s='';for(var i=0;i<a.length;i++)s+=('0'+((a[i]&255).toString(16))).slice(-2);return s;}
 function bytes(s){return new java.lang.String(s).getBytes(UTF);}
 function privateValue(className,name,obj){var f=Java.type(className).class.getDeclaredField(name);f.setAccessible(true);return f.get(obj);}
 function configHash(){var w=new java.io.StringWriter();C.createSerializer().write(m,w);return hash(bytes(String(w)));}
 eval(read(root+'automation/paste/waste-prime.cjs'));
 eval(read(root+'automation/paste/contiguous-linear-counts.cjs'));
 eval(read(root+'automation/paste/ftp-pad-group.cjs'));
 eval(read(root+'automation/paste/ftp-inline-conditioning.cjs'));
 eval(read(root+'automation/paste/ftp-registration-revalidation.cjs'));
 eval(read(root+'automation/paste/fast-camera-inspection.cjs'));
 eval(read(root+'automation/paste/ftp-one-pad-cleanup.cjs'));
 eval(read(root+'automation/paste/ftp-two-pad.cjs'));
 eval(read(root+'automation/paste/commissioning-stroke.cjs'));
 eval(read(root+'automation/paste/application-restart-continuity.cjs'));
 eval(read(root+'automation/paste/position-barrier.cjs'));
 eval(read(root+'automation/paste/manual-home-ledger-anchor.cjs'));
 eval(read(root+'automation/paste/waste-prime-native-preview.js'));
 eval(read(root+'automation/paste/native-air.cjs'));
 eval(read(root+'automation/paste/connection-policy.cjs'));
 function freeze(value){if(value&&typeof value==='object'){Object.keys(value).forEach(function(k){freeze(value[k]);});Object.freeze(value);}return value;}
 // Per-dispatch cache only: bytes are re-read and re-hashed at every call site;
 // cached objects are deeply frozen and keyed by canonical path plus digest.
 var frozenEvidenceJson=Object.create(null);
 function parseFrozenEvidence(data,e){var key=String(new F(e.path).getCanonicalPath())+'#'+e.sha256;if(Object.prototype.hasOwnProperty.call(frozenEvidenceJson,key))return frozenEvidenceJson[key];var parsed=freeze(JSON.parse(String(new java.lang.String(data,UTF))));frozenEvidenceJson[key]=parsed;return parsed;}
 var q=JSON.parse(read(root+'automation/plans/paste-contiguous-batch-request.json')),jvm=Number(Java.type('java.lang.management.ManagementFactory').getRuntimeMXBean().getStartTime());
 freeze(q);CommissioningStroke.validateBatch(q,Number(java.lang.System.currentTimeMillis()),jvm);
 var barrierFile=new F(q.barrierEvidence.path);if(!barrierFile.isFile())throw Error('Position barrier evidence missing');var barrierBytes=Fs.readAllBytes(barrierFile.toPath());if(hash(barrierBytes)!==q.barrierEvidence.sha256)throw Error('Position barrier evidence changed');var barrierRecord=parseFrozenEvidence(barrierBytes,q.barrierEvidence);PasteWastePrime.barrier(barrierRecord,q,Number(java.lang.System.currentTimeMillis()));
 function boundJson(e){var data=Fs.readAllBytes(new F(e.path).toPath());if(hash(data)!==e.sha256)throw Error('Bound evidence changed');return parseFrozenEvidence(data,e);}
 function manualHomeRead(e,json){var data=Fs.readAllBytes(new F(e.path).toPath());if(hash(data)!==e.sha256)throw Error('Manual-home evidence changed');return json?parseFrozenEvidence(data,e):String(new java.lang.String(data,UTF));}
 var manualHomeLedgerContinuity=null;if(q.manualHomeLedgerAnchorEvidence)manualHomeLedgerContinuity=PasteManualHomeLedgerAnchor.validate(boundJson(q.manualHomeLedgerAnchorEvidence),q,manualHomeRead,Number(java.lang.System.currentTimeMillis()));
 function ftpEvidence(e,json){var b=Fs.readAllBytes(new F(e.path).toPath());if(hash(b)!==e.sha256)throw Error('FTP source changed');return json?parseFrozenEvidence(b,e):null;}
 var applicationRestartContext=null;if(q.applicationRestartEvidence){var restartRecord=boundJson(q.applicationRestartEvidence);applicationRestartContext=PasteApplicationRestartContinuity.validate(restartRecord,q,ftpEvidence,Number(java.lang.System.currentTimeMillis()));}
 function verifyFtpSources(){if(PasteFtpTwoPad.isFtp(q))PasteFtpTwoPad.verifySources(q,ftpEvidence);}
 verifyFtpSources();
 var measuredProfile=boundJson(q.profileEvidence),nativePreviewRecord=boundJson(q.nativePreviewEvidence),primeLedgerEvidence=boundJson(q.primeLedgerEvidence),priorLedgerEvidence=boundJson(q.priorLedgerEvidence),carryover=boundJson(q.carryoverEvidence);
 var budgetAmendmentContext=null;if(q.budgetAmendmentEvidence){var amendmentRecord=boundJson(q.budgetAmendmentEvidence),anchorLedger=boundJson(amendmentRecord.anchorLedgerEvidence),anchorReport=boundJson(amendmentRecord.anchorReportEvidence);if(JSON.stringify(q.budgetAmendmentEvidence.anchorLedgerEvidence)!==JSON.stringify(amendmentRecord.anchorLedgerEvidence)||JSON.stringify(q.budgetAmendmentEvidence.anchorReportEvidence)!==JSON.stringify(amendmentRecord.anchorReportEvidence))throw Error('Request amendment anchor paths differ from hash-bound amendment');budgetAmendmentContext={record:amendmentRecord,anchorLedger:anchorLedger,anchorReport:anchorReport,anchorLedgerSha256:amendmentRecord.anchorLedgerEvidence.sha256,anchorReportSha256:amendmentRecord.anchorReportEvidence.sha256,applicationRestartContinuity:applicationRestartContext,manualHomeLedgerContinuity:manualHomeLedgerContinuity||(applicationRestartContext&&applicationRestartContext.manualHomeLedgerContinuity)||null};}
 if(nativePreviewRecord.status!=='completed-model-only-contiguous-batch-preview'||nativePreviewRecord.noControllerAccess!==true||nativePreviewRecord.noMotion!==true||nativePreviewRecord.id!==q.id||nativePreviewRecord.jvmStartMs!==q.jvmStartMs||nativePreviewRecord.liveConfigurationSha256!==q.liveConfigurationSha256||!nativePreviewRecord.stages||nativePreviewRecord.stages.length!==q.previewStages.length)throw Error('Exact detached batch preview required');
 if(nativePreviewRecord.request.scope!==(PasteFtpTwoPad.isFtp(q)?PasteFtpTwoPad.scope(true,q):q.scope==='contiguous-native-scrap-sequence-comparison'?'contiguous-native-scrap-sequence-comparison-preview':'contiguous-native-scrap-batch-preview')||!PasteFtpTwoPad.same(nativePreviewRecord.request.ftpTargetRecord,q.ftpTargetRecord)||!PasteFtpTwoPad.same(nativePreviewRecord.request.ftpTargetEvidence,q.ftpTargetEvidence)||nativePreviewRecord.request.id!==q.id||nativePreviewRecord.request.mode!==q.mode||nativePreviewRecord.request.stopPath!==q.stopPath||JSON.stringify(nativePreviewRecord.request.rawBounds)!==JSON.stringify(q.rawBounds)||JSON.stringify(nativePreviewRecord.request.headClearanceBounds)!==JSON.stringify(q.headClearanceBounds)||nativePreviewRecord.request.xyClearanceRawZ!==q.xyClearanceRawZ||JSON.stringify(nativePreviewRecord.request.clearanceReviewEvidence)!==JSON.stringify(q.clearanceReviewEvidence)||JSON.stringify(nativePreviewRecord.request.receivingProfile)!==JSON.stringify(q.receivingProfile)||q.scope==='contiguous-native-scrap-sequence-comparison'&&(nativePreviewRecord.request.targetSurface!==q.targetSurface||nativePreviewRecord.request.sequenceProtocol!==q.sequenceProtocol))throw Error('Preview safety bounds/profile differ');
 PasteWastePrime.compareExact(nativePreviewRecord.before.raw,q.expectedRaw,'preview start');PasteWastePrime.compareExact(nativePreviewRecord.before.driver,q.expectedDriver,'preview driver');PasteWastePrime.compareExact(nativePreviewRecord.after.raw,q.expectedRaw,'preview unchanged raw');PasteWastePrime.compareExact(nativePreviewRecord.after.driver,q.expectedDriver,'preview unchanged driver');
 q.previewStages.forEach(function(stage,i){var p=nativePreviewRecord.stages[i],spec=nativePreviewRecord.request.previewStages[i],dwell=stage.dwellMilliseconds===undefined?0:stage.dwellMilliseconds,previewDwell=spec.dwellMilliseconds===undefined?0:spec.dwellMilliseconds;PasteWastePrime.compareExact(p.startRaw,stage.startRaw,'preview stage start');PasteWastePrime.compareExact(p.targetRaw,stage.targetRaw,'preview stage target');if(p.axis!==stage.axis||p.speedFraction!==stage.speedFraction||p.dwellMilliseconds!==dwell||previewDwell!==dwell||JSON.stringify(p.expandedCommands)!==JSON.stringify(stage.expandedCommands)||p.sha256!==stage.sha256||p.path!==stage.path||hash(Fs.readAllBytes(new F(stage.path).toPath()))!==stage.sha256||JSON.stringify(spec.gapEvidence||null)!==JSON.stringify(stage.gapEvidence||null)||spec.estimatedGapMm!==stage.estimatedGapMm||spec.gapUncertaintyMm!==stage.gapUncertaintyMm||JSON.stringify(spec.wipeReviewEvidence||null)!==JSON.stringify(stage.wipeReviewEvidence||null)||spec.wipeReview!==stage.wipeReview)throw Error('Preview stage or safety evidence differs from request');});
 if(primeLedgerEvidence.status!=='verified'||primeLedgerEvidence.sessionId!==q.sessionId||primeLedgerEvidence.lastVerifiedB!==-240||primeLedgerEvidence.reservedDegrees!==960||carryover.primeLedgerSha256!==q.primeLedgerEvidence.sha256||carryover.priorLedgerSha256!==q.priorLedgerEvidence.sha256||carryover.priorSessionId!==priorLedgerEvidence.sessionId||priorLedgerEvidence.status!=='verified'||priorLedgerEvidence.reservedDegrees!==10940||carryover.priorGrossDegrees!==10940||carryover.manualDisplacementUnknown!==true||carryover.verifiedPrimeDegrees!==960||carryover.startB!==-240||carryover.maximumAbsoluteDegrees!==120)throw Error('Current hash-bound syringe carryover evidence required');
 if(measuredProfile.sessionId!==q.sessionId||measuredProfile.jvmStartMs!==q.jvmStartMs||measuredProfile.liveConfigurationSha256!==q.liveConfigurationSha256||measuredProfile.syringeId!==q.syringeId||measuredProfile.flowCalibrated!==false||measuredProfile.provenance!=='commissioning-provisional'||measuredProfile.precisionCalibrated!==false||!measuredProfile.measurementEvidence||q.receivingProfile.sha256!==q.profileEvidence.sha256||q.receivingProfile.provenance!==measuredProfile.provenance||q.receivingProfile.basis!==measuredProfile.basis||q.receivingProfile.estimatedGapMm!==measuredProfile.estimatedGapMm||q.receivingProfile.gapUncertaintyMm!==measuredProfile.gapUncertaintyMm)throw Error('Same-session measured profile/configuration required');
 ['X','Y','Z','A'].forEach(function(k){PasteWastePrime.close(q.receivingProfile.rawPose[k],measuredProfile.rawPose[k],0.0001,'profile raw '+k);});
 var profileMeasurement=Fs.readAllBytes(new F(measuredProfile.measurementEvidence.path).toPath());if(hash(profileMeasurement)!==measuredProfile.measurementEvidence.sha256)throw Error('Measured receiving-profile evidence changed');
 if(hash(Fs.readAllBytes(new F(q.clearanceReviewEvidence.path).toPath()))!==q.clearanceReviewEvidence.sha256)throw Error('Clearance review evidence changed');q.previewStages.forEach(function(s){if(s.wipeReview&&hash(Fs.readAllBytes(new F(s.wipeReviewEvidence.path).toPath()))!==s.wipeReviewEvidence.sha256)throw Error('Wipe review evidence changed');if(s.axis==='B'&&hash(Fs.readAllBytes(new F(s.gapEvidence.path).toPath()))!==s.gapEvidence.sha256)throw Error('B-stage gap evidence changed');});
 var imageBytes=Fs.readAllBytes(new F(q.reviewedImageEvidence.path).toPath());if(hash(imageBytes)!==q.reviewedImageEvidence.sha256)throw Error('Fresh reviewed pose/clearance image changed');
 var panel=Java.type('org.openpnp.gui.MainFrame').get().getJobTab(),state=panel.getClass().getDeclaredField('state');state.setAccessible(true);
 if(m.getDrivers().size()!==1)throw Error('Unexpected driver topology');var d=m.getDrivers().get(0);
 if(String(d.getClass().getName())!=='org.openpnp.machine.reference.driver.GcodeDriver'||String(d.getId())!=='DRV16982438146c1dd4')throw Error('Unknown driver');
 if(String(planner.getClass().getName())!=='org.openpnp.machine.reference.driver.NullMotionPlanner')throw Error('Only audited NullMotionPlanner allowed');
 var nativePositionAckTimeout=Number(privateValue('org.openpnp.machine.reference.driver.GcodeDriver','infinityTimeoutMilliseconds',d));if(!isFinite(nativePositionAckTimeout)||nativePositionAckTimeout<=0||nativePositionAckTimeout>60000)throw Error('Unreviewed position ACK timeout');
 var jar=new F(d.getClass().getProtectionDomain().getCodeSource().getLocation().toURI());if(hash(Fs.readAllBytes(jar.toPath()))!=='bcd34923ae91d61a96b98b4c82c93cdc90093ff94292270fd0a18fc6f96f7752')throw Error('Installed native API binary changed');
 var head=m.getDefaultHead(),left=head.getNozzleByName('N1'),right=head.getNozzleByName('N2'),top=head.getDefaultCamera(),bottom=null;
 for each(var camera in m.getCameras())if(String(camera.getLooking())==='Up'){if(bottom!==null)throw Error('Multiple bottom cameras');bottom=camera;}
 if(left==null||right==null||top==null||bottom==null||String(left.getId())!=='N1'||String(top.getId())!=='CAM1607555396816'||String(top.getLooking())!=='Down'||String(right.getId())!=='NOZ1710829fd33a0170')throw Error('Unexpected nozzles/cameras');
 var items={N1:left,N2:right,top:top,bottom:bottom};
 function pose(n){var p=n.getLocation().convertToUnits(MM);return {x:Number(p.getX()),y:Number(p.getY()),z:Number(p.getZ()),rotation:Number(p.getRotation())};}
 function poses(){var a={};Object.keys(items).forEach(function(k){a[k]=pose(items[k]);});return a;}
 function comparePoses(a,b){Object.keys(items).forEach(function(k){['x','y','z','rotation'].forEach(function(axis){PasteWastePrime.close(a[k][axis],b[k][axis],0.0001,k+' pose '+axis);});});}
 function compareStagePoses(a,b,stage){var delta=stage.targetRaw[stage.axis]-stage.startRaw[stage.axis];['N1','N2','top','bottom'].forEach(function(k){['x','y','z','rotation'].forEach(function(axis){var change=0;if(stage.axis==='B'&&k==='N2'&&axis==='rotation')change=delta;if(stage.axis==='Z'&&axis==='z')change=k==='N1'?delta:k==='N2'?-delta:0;if((stage.axis==='X'&&axis==='x'||stage.axis==='Y'&&axis==='y')&&k!=='bottom')change=delta;PasteWastePrime.close(b[k][axis],a[k][axis]+change,0.0001,'batch native polarity '+k+' '+axis);});});}
 function compareStageCounts(before,after,stage){if(stage.axis==='B'){['X','Y','Z','A'].forEach(function(k){if(before[k]!==after[k])throw Error('Other controller axis count changed in B stage');});if(before.B!==PasteWastePrime.countB(stage.startRaw.B)||after.B!==PasteWastePrime.countB(stage.targetRaw.B))throw Error('B count target mismatch');}else PasteContiguousLinearCounts.compare(before,after,stage);}
 var axes={},ids={X:'AXS169824381580efcb',Y:'AXS16982438158c4660',Z:'AXS16982438158d0458',A:'AXS16b068df4e35374e',B:'AXS17108288e61da5fb'};
 for each(var a in new AL(m).drivenBy(d).getControllerAxes()){var letter=String(a.getLetter());if(!ids[letter]||String(a.getId())!==ids[letter]||axes[letter])throw Error('Unexpected raw axis');axes[letter]=a;}
 if(Object.keys(axes).sort().join(',')!=='A,B,X,Y,Z')throw Error('Missing raw axis');
 function projectedPoses(raw){var result={};Object.keys(items).forEach(function(k){var n=items[k],location=n.getMappedAxes(m);Object.keys(axes).forEach(function(a){location=location.put(new AL(axes[a],raw[a]));});var p=n.toHeadMountableLocation(n.toTransformed(location)).convertToUnits(MM);result[k]={x:Number(p.getX()),y:Number(p.getY()),z:Number(p.getZ()),rotation:Number(p.getRotation())};});return result;}
 function snapshot(){var s={raw:{},driver:{},nativePoses:poses()};Object.keys(axes).forEach(function(k){s.raw[k]=Number(axes[k].getCoordinate());s.driver[k]=Number(axes[k].getDriverCoordinate());});return s;}
 var originalReader=privateValue('org.openpnp.machine.reference.driver.GcodeDriver','readerThread',d),originalCommands=d.commands;
 var permitClearanceLiftOnStop=false;
 function stopRequested(){return new F(q.stopPath).exists();}
 function supervisionGate(){if(stopRequested()&&!permitClearanceLiftOnStop){if(typeof r!=='undefined'&&r){r.cooperativeStopRequested=true;r.stopAtClearance=snapshot().raw.Z===q.xyClearanceRawZ;}throw Error('Cooperative stop requested; no further native stage');}}
 function verifyTravelReview(){if(budgetAmendmentContext){var travel=CommissioningStroke.budgetTravelReview(q,budgetAmendmentContext.record);if(travel)boundJson(travel);}}
 function stateGate(){verifyTravelReview();supervisionGate();
  if(d.isInSimulationMode()||String(d.getCommunicationsType())!=='serial')throw Error('Physical native serial owner required');
  var activeExecutor=privateValue('org.openpnp.spi.base.AbstractMachine','executor',m),owned=m.isTask(java.lang.Thread.currentThread());if(activeExecutor==null||activeExecutor.isShutdown()||activeExecutor.isTerminated()||activeExecutor.getCorePoolSize()!==1||activeExecutor.getMaximumPoolSize()!==1||activeExecutor.getActiveCount()!==(owned?1:0)||!activeExecutor.getQueue().isEmpty()||(executor!=null&&activeExecutor!==executor))throw Error('Exact idle/owned single native executor required');

  if(d.commands!==originalCommands||originalReader==null||!originalReader.isAlive()||privateValue('org.openpnp.machine.reference.driver.GcodeDriver','readerThread',d)!==originalReader||privateValue('org.openpnp.machine.reference.driver.GcodeDriver','errorResponse',d)!=null)throw Error('Reader/commands changed or prior native error');
  if((m.isBusy()&&!m.isTask(java.lang.Thread.currentThread()))||!m.isEnabled()||!m.isHomed()||String(state.get(panel))!=='Stopped')throw Error('Need idle enabled homed machine, stopped job');
  if(String(privateValue('org.openpnp.machine.reference.driver.GcodeDriver','connected',d))!=='true'||d.isMotionPending())throw Error('Driver disconnected or prior motion pending');
  if(privateValue('org.openpnp.machine.reference.driver.AbstractMotionPlanner','motionCommands',planner).size()!==0)throw Error('Prior native motion queued');
  for each(var h in m.getHeads())for each(var n in h.getNozzles())if(n.getPart()!=null||n.getPartsFeeder()!=null)throw Error('Held/associated part');
  if(right.getNozzleTip()!=null||right.getCompatibleNozzleTips().size()!==0||right.getRotationModeOffset()!=null||right.isChangerEnabled()||right.getManualNozzleTipChangeLocation().isInitialized()||m.getPnpJobProcessor().isPreRotateAllNozzles())throw Error('N2 quarantine changed');
  for each(var actuator in head.getActuators())if(actuator.isInterlockActuator()||actuator.getInterlockMonitor()!=null)throw Error('Head actuator interlock could actuate during native move');
  var mapped=[];for each(var axis in top.getMappedAxes(m).getControllerAxes()){mapped.push(String(axis.getLetter()));if(String(axis.getType())==='Rotation')throw Error('Top camera maps a physical rotation axis');}
  if(mapped.sort().join(',')!=='X,Y')throw Error('Top camera must map only physical X/Y (no Z/A/B)');
  var offsets=privateValue('org.openpnp.machine.reference.driver.AbstractMotionPlanner','lastDirectionalBacklashOffset',planner);
  for each(var axis in offsets.getAxes())if(Math.abs(Number(offsets.getCoordinate(axis)))>1e-9)throw Error('Unresolved directional backlash offset');
  var subordinate=privateValue('org.openpnp.machine.reference.driver.AbstractMotionPlanner','subordinateMotion',planner);
  var subordinateQueue=privateValue('org.openpnp.machine.reference.driver.AbstractMotionPlanner$SubordinateMotion','queue',subordinate);
  if(subordinateQueue!=null&&!subordinateQueue.isEmpty())throw Error('Prior subordinate axes queued');
  if(String(axes.B.getType())!=='Rotation'||axes.B.isLimitRotation()||axes.B.isWrapAroundRotation()||!axes.B.isInvertLinearRotational())throw Error('Literal controller-linear B semantics not configured');
  if(Number(axes.B.getFeedratePerSecond().convertToUnits(MM).getValue())!==100||Number(axes.B.getAccelerationPerSecond2().convertToUnits(MM).getValue())!==500||Number(axes.B.getJerkPerSecond3().convertToUnits(MM).getValue())!==2000)throw Error('B rate/acceleration/jerk changed');
  if(String(axes.B.getBacklashCompensationMethod())!=='None'||Number(axes.B.getBacklashOffset().convertToUnits(MM).getValue())!==0)throw Error('Unexpected B backlash');
  ['X','Y'].forEach(function(k){if(['None','OneSidedPositioning'].indexOf(String(axes[k].getBacklashCompensationMethod()))<0)throw Error('Unaudited XY backlash method');});
  if(String(axes.Z.getType())!=='Z'||String(axes.Z.getBacklashCompensationMethod())!=='DirectionalCompensation'||Number(axes.Z.getBacklashOffset().convertToUnits(MM).getValue())!==0||Number(axes.Z.getSneakUpOffset().convertToUnits(MM).getValue())!==0||Number(axes.Z.getFeedratePerSecond().convertToUnits(MM).getValue())!==200)throw Error('Audited raw Z mapping/backlash/feed changed');
  if(String(d.getMotionControlType())!=='ConstantAcceleration'||String(d.getUnits())!=='Millimeters')throw Error('Unaudited controller motion mode/units');
  if(Number(planner.getMinimumSpeed())!==0.05)throw Error('Audited native minimum speed changed');
  if(Number(d.getTimeoutMilliseconds())!==10000)throw Error('Reviewed original driver timeout changed');
  var completeRegex=d.getCommand(top,CT.MOVE_TO_COMPLETE_REGEX);if(completeRegex!=null&&String(completeRegex).trim())throw Error('Native completion regex could hide responses');
  if(String(d.getCommand(null,CT.COMMAND_CONFIRM_REGEX)).trim()!=='^ok.*')throw Error('Native ACK regex changed');
  if(String(d.getCommand(null,CT.COMMAND_ERROR_REGEX))!==NativePasteAir.nativeErrorRegex)throw Error('Native per-line error/reset latch absent or unaudited; activation blocked');
  var moveTemplate=PasteConnectionPolicy.tokens(d.getCommand(top,CT.MOVE_TO_COMMAND));
  if(JSON.stringify(moveTemplate)!==JSON.stringify(['{Acceleration:M204 S%.0f }','G1 {X:X%.4f} {Y:Y%.4f} {Z:Z%.4f} {A:A%.4f} {B:B%.4f} {FeedRate:F%.0f}']))throw Error('Native motion template changed');
  if(['M114','M114 ; get position'].indexOf(String(d.getCommand(null,CT.GET_POSITION_COMMAND)).trim())<0)throw Error('Position query command changed');
  if(JSON.stringify(PasteConnectionPolicy.tokens(d.getCommand(top,CT.MOVE_TO_COMPLETE_COMMAND)))!==JSON.stringify(['M400']))throw Error('Motion completion command changed');
 }
 stateGate();if(configHash()!==q.liveConfigurationSha256)throw Error('Live configuration changed');
 var executor=privateValue('org.openpnp.spi.base.AbstractMachine','executor',m);
 if(executor==null||executor.isShutdown()||executor.isTerminated()||executor.getCorePoolSize()!==1||executor.getMaximumPoolSize()!==1||executor.getActiveCount()!==0||!executor.getQueue().isEmpty())throw Error('Existing native single-worker executor must be idle; no second executor is created');
 var taskSetter=Java.type('org.openpnp.spi.base.AbstractMachine').class.getDeclaredMethod('setTaskThread',Java.type('java.lang.Thread').class);taskSetter.setAccessible(true);
 function taskOwner(thread){taskSetter.invoke(m,Java.to([thread],'java.lang.Object[]'));}
 function settle(){var delay=Math.max(200,Number(top.getSettleTimeMs()),Number(bottom.getSettleTimeMs()));if(!isFinite(delay)||delay>3000)throw Error('Unreviewed camera settle interval');java.lang.Thread.sleep(Math.ceil(delay));}
 var initial=snapshot();PasteWastePrime.compareExact(initial.raw,q.expectedRaw,'expected raw');PasteWastePrime.compareExact(initial.driver,q.expectedDriver,'expected driver');comparePoses(initial.nativePoses,q.expectedNativePoses);
 var out=new F(root+'automation/evidence/paste-contiguous-batch-'+q.id);if(!out.mkdir())throw Error('Commissioning stroke UUID already claimed; no retry');
 var r={schema:1,id:q.id,status:'claimed',startedAt:new Date().toISOString(),request:q,beforeQuerySnapshot:initial,transitions:[],motionSubmitted:false,positionQueryAckTimeoutMs:nativePositionAckTimeout,nativeMinimumSpeed:0.05,physicalAcceptanceEstablished:false,calibrationEstablished:false,noReplay:true};
 function save(status){r.status=status;r.transitions.push({status:status,time:new Date().toISOString()});Fs.write(new F(out,'report.json').toPath(),bytes(JSON.stringify(r,null,2)+'\n'));if(status==='completed-contiguous-batch-awaiting-observation')uiStatus('Paste wet batch complete — awaiting inspection; physical acceptance pending');else if(status==='completed-contiguous-air-batch-awaiting-observation')uiStatus('Paste air batch complete — awaiting inspection; physical acceptance pending');else if(status==='failed-no-retry-no-recovery-motion'||status==='stopped-contiguous-batch-no-retry'||status==='reconciliation-failed-no-retry-no-refund')uiStatus('Paste '+q.mode+' batch stopped/faulted — no retry; inspect report');else if(status==='enqueue-failed-no-motion')uiStatus('Paste '+q.mode+' batch failed to start — inspect report');}
 save('preflight-before-any-controller-query');
 var ledger=null,ledgerFile=null;
 var lastReported=null;
 var positionRegex='^.*X:(?<X>-?\\d+\\.\\d+)\\s*Y:(?<Y>-?\\d+\\.\\d+)\\s*Z:(?<Z>-?\\d+\\.\\d+)\\s*A:(?<A>-?\\d+\\.\\d+)\\s*B:(?<B>-?\\d+\\.\\d+).*';
 if(String(d.getCommand(null,CT.POSITION_REPORT_REGEX))!==positionRegex)throw Error('Audited position-report delimiter changed');
 var positionPattern=java.util.regex.Pattern.compile(positionRegex);
 function query(saved,label){
  var entry={saved:saved,priorResponses:[],responses:[]};r[label]=entry;
  // Inspect pending motion/M400 responses before sending the read-only query.
  append(d.receiveResponses(),entry.priorResponses);checkedLines(entry.priorResponses);
  if(entry.priorResponses.some(function(line){return positionPattern.matcher(line).matches();}))throw Error('Stale position response before fresh query');
  r.transportUncertain=true;r.controllerQuerySubmitted=true;save(label+'-query-started');
  var observed=d.getReportedLocation(3000),reported={};for each(var a in observed.getControllerAxes())reported[String(a.getLetter())]=Number(observed.getCoordinate(a));
  collect(positionRegex,entry);
  var delimiter=-1;entry.responses.forEach(function(line,i){if(positionPattern.matcher(line).matches())delimiter=i;});
  if(delimiter<0)throw Error('Fresh M114 delimiter missing');
  var ackAfter=entry.responses.slice(delimiter+1).some(function(line){return /^ok/.test(line);});
  if(!ackAfter)collect('^ok.*',entry);
  append(d.receiveResponses(),entry.responses);checkedLines(entry.responses);
  entry.reported=reported;entry.counts=PasteWastePrime.fullResponse(entry.responses,reported,saved.raw);save(label+'-reported');PasteWastePrime.compareReported(reported,saved.raw,saved.driver);r.transportUncertain=false;lastReported=reported;return reported;
 }
 function append(javaLines,target){for each(var line in javaLines)target.push(String(line.getLine()));}
 function checkedLines(lines){PasteConnectionPolicy.responses(lines);lines.forEach(function(line){if(/unknown command|halted|fatal|\bkilled\b/i.test(line))throw Error('Controller fault: '+line);});}
 function collect(regex,entry){var list=d.receiveResponses(regex,3000,new (Java.type('org.openpnp.machine.reference.driver.GcodeDriver$TimeoutAction'))({apply:function(lines){append(lines,entry.responses);checkedLines(entry.responses);save('response-timeout');throw new java.lang.Exception('Native B response timeout; no retry');}}));append(list,entry.responses);checkedLines(entry.responses);}
 function capture(camera,name){
  if(String(camera.getClass().getName())!=='org.openpnp.machine.reference.camera.OpenPnpCaptureCamera')throw Error('Unknown camera capture implementation');
  var open=camera.getClass().getDeclaredMethod('isOpen');open.setAccessible(true);if(!open.invoke(camera))throw Error('Camera stream not already open; no reopen');
  var image=camera.captureRaw();if(image==null||!I.write(image,'png',new F(out,name+'.png')))throw Error('Raw capture failed');return {image:image,path:name+'.png',width:image.getWidth(),height:image.getHeight()};
 }
 function pair(a,b,name){var BI=Java.type('java.awt.image.BufferedImage'),canvas=new BI(a.image.getWidth()+b.image.getWidth(),Math.max(a.image.getHeight(),b.image.getHeight()),BI.TYPE_INT_RGB),g=canvas.createGraphics();try{g.drawImage(a.image,0,0,null);g.drawImage(b.image,a.image.getWidth(),0,null);}finally{g.dispose();}if(!I.write(canvas,'png',new F(out,name+'.png')))throw Error('Contact sheet write failed');}
 save('queued-on-existing-native-executor');
 try{executor.submit(new (Java.type('java.util.concurrent.Callable'))({call:function(){
 var ownedTask=false,keepBusy=false;
 try{
  if(m.isBusy()||!executor.getQueue().isEmpty())throw Error('Native task ownership changed before commissioning stroke');
  taskOwner(java.lang.Thread.currentThread());ownedTask=true;m.fireMachineBusy(true);
  verifyFtpSources();CommissioningStroke.validateBatch(q,Number(java.lang.System.currentTimeMillis()),jvm);PasteWastePrime.barrier(barrierRecord,q,Number(java.lang.System.currentTimeMillis()));stateGate();
  if(configHash()!==q.liveConfigurationSha256)throw Error('Configuration changed before native task');
  var taskStart=snapshot();PasteWastePrime.compareExact(taskStart.raw,initial.raw,'queued raw');PasteWastePrime.compareExact(taskStart.driver,initial.driver,'queued driver');comparePoses(taskStart.nativePoses,initial.nativePoses);
  var sessionDir=new F(root+'automation/evidence/paste-commissioning-stroke-session-'+q.sessionId);
  if(q.previousLedgerSha256===null||!sessionDir.isDirectory())throw Error('Batch requires existing verified commissioning ledger');
  ledgerFile=new F(sessionDir,'ledger.json');var previous=null;
  {var oldBytes=Fs.readAllBytes(ledgerFile.toPath());if(hash(oldBytes)!==q.previousLedgerSha256)throw Error('Commissioning ledger changed');previous=JSON.parse(String(new java.lang.String(oldBytes,UTF)));var priorReport=boundJson(q.previousReportEvidence),priorEntry=previous.entries[previous.entries.length-1];CommissioningStroke.validatePreviousReport(priorReport,previous,q.previousLedgerSha256,q.imageCapturedMs);r.priorCompletedReportEvidence=q.previousReportEvidence;}
  if(q.mode==='wet'){ledger=CommissioningStroke.reserveBatch(previous,q,carryover,budgetAmendmentContext);var reservedBytes=bytes(JSON.stringify(ledger,null,2)+'\n');Fs.write(ledgerFile.toPath(),reservedBytes);if(hash(Fs.readAllBytes(ledgerFile.toPath()))!==hash(reservedBytes))throw Error('Budget reservation write not verified');r.reservedAbsoluteDegrees=ledger.totalAbsoluteDegrees;r.lastVerifiedB=ledger.lastVerifiedB;r.ledgerPath=String(ledgerFile);save('budget-reserved-before-query-and-B-command');}else{if(!previous||previous.status!=='verified'||previous.lastVerifiedB!==q.expectedRaw.B)throw Error('Air batch requires verified unchanged ledger');r.observedLedgerSha256=q.previousLedgerSha256;save('air-ledger-read-only');}
  query(initial,'before');PasteWastePrime.compareExact(snapshot().raw,initial.raw,'post-query unchanged raw');
  settle();var beforeTop=capture(top,'top-before-raw'),beforeBottom=capture(bottom,'bottom-before-raw');r.beforeImages={top:{path:beforeTop.path,width:beforeTop.width,height:beforeTop.height},bottom:{path:beforeBottom.path,width:beforeBottom.width,height:beforeBottom.height}};save('before-images-captured');
  verifyFtpSources();CommissioningStroke.validateBatch(q,Number(java.lang.System.currentTimeMillis()),jvm);PasteWastePrime.barrier(barrierRecord,q,Number(java.lang.System.currentTimeMillis()));stateGate();if(configHash()!==q.liveConfigurationSha256)throw Error('Configuration changed during preflight');
  if(!executor.getQueue().isEmpty())throw Error('Competing native work queued during camera preflight');
  var preMove=snapshot();PasteWastePrime.compareExact(preMove.raw,initial.raw,'unchanged pre-move raw');comparePoses(preMove.nativePoses,initial.nativePoses);PasteWastePrime.compareReported(r.before.reported,preMove.raw,preMove.driver);
  // Validate every target and both-head transformation before dispensing.
  var predicted=initial.nativePoses;
  q.previewStages.forEach(function(stage){var target=new AL(axes[stage.axis],stage.targetRaw[stage.axis]);if(!planner.isValidLocation(top,target))throw Error('Cycle target outside native limits');if(axes[stage.axis].isSoftLimitLowEnabled()&&stage.targetRaw[stage.axis]<Number(axes[stage.axis].getSoftLimitLow().convertToUnits(MM).getValue())||axes[stage.axis].isSoftLimitHighEnabled()&&stage.targetRaw[stage.axis]>Number(axes[stage.axis].getSoftLimitHigh().convertToUnits(MM).getValue()))throw Error('Batch stage outside configured limits');var next=projectedPoses(stage.targetRaw);compareStagePoses(predicted,next,stage);['N1','N2'].forEach(function(k){var b=q.headClearanceBounds[k];['x','y','z'].forEach(function(a){var u=a.toUpperCase();if(next[k][a]<b['min'+u]||next[k][a]>b['max'+u])throw Error('Both-head clearance bound exceeded '+k+' '+a);});});predicted=next;});
  r.stages=[];r.commandedControllerAxes=['X','Y','Z','B'];var previousCounts=r.before.counts;
  q.previewStages.forEach(function(stage,index){
   uiStatus('Paste '+q.mode+' batch stage '+(index+1)+'/'+q.previewStages.length+' ('+stage.axis+')');
   if(stopRequested()){var stoppedAt=snapshot().raw,decision=CommissioningStroke.stopDecision(q,stoppedAt,stage,true);permitClearanceLiftOnStop=decision==='reviewed-clearance-lift';if(!permitClearanceLiftOnStop){r.cooperativeStopRequested=true;r.stopAtClearance=decision==='stop-at-clearance';throw Error('Cooperative stop before next stage; no unreviewed recovery motion');}r.clearanceLiftOnStop=true;}
   stateGate();if(configHash()!==q.liveConfigurationSha256)throw Error('Configuration changed during batch');
   if(PasteFtpTwoPad.isFtp(q)&&q.ftpTargetRecord.compensatedSequence&&index===q.ftpTargetRecord.pads[0].restoreStageIndex){verifyFtpSources();if(PasteFtpInlineConditioning.isInline(q)){r.inlineTransferElapsedMilliseconds=PasteFtpInlineConditioning.entry(q,Number(java.lang.System.currentTimeMillis()),r.stages);}else PasteFtpTwoPad.entryTime(q,Number(java.lang.System.currentTimeMillis()));}
   var start=snapshot();PasteWastePrime.compareExact(start.raw,stage.startRaw,'cycle intermediate start');PasteWastePrime.compareReported(lastReported,start.raw,start.driver);
   var fullStart=new AL(),fullEnd=new AL();Object.keys(axes).forEach(function(a){fullStart=fullStart.put(new AL(axes[a],stage.startRaw[a]));fullEnd=fullEnd.put(new AL(axes[a],stage.targetRaw[a]));});
   var motion=new (Java.type('org.openpnp.model.Motion'))(top,fullStart,fullEnd,stage.speedFraction,MO.SpeedOverPrecision),commands=motion.interpolatedMoveToCommands(d,false);if(commands.size()!==1)throw Error('Single-axis cycle stage projection required');var command=commands.get(0),moved=command.getMovedAxesLocation();if(moved.getControllerAxes().size()!==1||!moved.contains(axes[stage.axis])||Math.abs(Number(moved.getCoordinate(axes[stage.axis]))-stage.targetRaw[stage.axis])>.0001)throw Error('Cycle projection changes other axes');
   var formatter=PasteWastePrimeNativePreview.preview(d,command,String(d.getCommand(top,CT.MOVE_TO_COMMAND)));if(JSON.stringify(formatter.expandedCommands)!==JSON.stringify(stage.expandedCommands))throw Error('Actual stage formatter differs from detached cumulative preview');
   var record={index:index,axis:stage.axis,startRaw:stage.startRaw,targetRaw:stage.targetRaw,formatter:formatter,startedAt:new Date().toISOString(),verified:false};r.stages.push(record);r.motionSubmitted=true;r.controllerPositionVerified=false;save('submitting-cycle-stage-'+index);
   if(PasteFtpInlineConditioning.isInline(q)&&index===q.ftpTargetRecord.pads[0].restoreStageIndex)r.inlineTransferElapsedMilliseconds=PasteFtpInlineConditioning.entry(q,Number(java.lang.System.currentTimeMillis()),r.stages);
   planner.moveTo(top,new AL(axes[stage.axis],stage.targetRaw[stage.axis]),stage.speedFraction,MO.SpeedOverPrecision);
   record.nativeMotionCompletionReported=true;var after=snapshot();PasteWastePrime.compareExact(after.raw,stage.targetRaw,'cycle target');compareStagePoses(start.nativePoses,after.nativePoses,stage);query(after,'stage'+index);compareStageCounts(previousCounts,r['stage'+index].counts,stage);previousCounts=r['stage'+index].counts;r.controllerPositionVerified=true;r.countsVerified=true;
   record.verified=true;record.finishedAt=new Date().toISOString();r.afterQuerySnapshot=after;save('verified-cycle-stage-'+index);permitClearanceLiftOnStop=false;if(r.clearanceLiftOnStop){r.cooperativeStopRequested=true;r.stopAtClearance=CommissioningStroke.stopDecision(q,after.raw,stage,true)==='stop-at-clearance';throw Error('Cooperative stop after reviewed clearance lift');}
   if(q.mode==='wet'&&stage.axis==='B'){ledger=CommissioningStroke.markBatchStep(ledger,q,index,r['stage'+index].reported.B);var progressBytes=bytes(JSON.stringify(ledger,null,2)+'\n');Fs.write(ledgerFile.toPath(),progressBytes);if(hash(Fs.readAllBytes(ledgerFile.toPath()))!==hash(progressBytes))throw Error('Cycle progress ledger write not verified');}
   var dwellMilliseconds=stage.dwellMilliseconds===undefined?0:stage.dwellMilliseconds;
   if(stage.axis==='B'&&dwellMilliseconds>0){var dwellStartNs=java.lang.System.nanoTime(),dwellDeadlineNs=dwellStartNs+dwellMilliseconds*1000000;record.dwell={requestedMilliseconds:dwellMilliseconds,startedAt:new Date().toISOString(),actualElapsedMilliseconds:0,stopObserved:false};save('post-B-dwell-started-'+index);while(true){if(stopRequested()){record.dwell.stopObserved=true;break;}var remainingNs=dwellDeadlineNs-java.lang.System.nanoTime();if(remainingNs<=0)break;java.lang.Thread.sleep(Math.min(50,Math.max(1,Math.ceil(remainingNs/1000000))));}record.dwell.actualElapsedMilliseconds=Number(java.lang.System.nanoTime()-dwellStartNs)/1000000;record.dwell.endedAt=new Date().toISOString();save('post-B-dwell-ended-'+index);}
   
  });
  r.after=r['stage'+(q.previewStages.length-1)];r.expectedAfterRaw=q.finalTargetRaw;r.nativeMotionCompletionReported=true;r.controllerPositionVerified=true;r.countsVerified=true;r.independentFirmwareStepVerified=true;
  settle();var afterTop=capture(top,'top-after-raw'),afterBottom=capture(bottom,'bottom-after-raw');r.afterImages={top:{path:afterTop.path,width:afterTop.width,height:afterTop.height},bottom:{path:afterBottom.path,width:afterBottom.width,height:afterBottom.height}};pair(beforeTop,afterTop,'top-before-after');pair(beforeBottom,afterBottom,'bottom-before-after');
  stateGate();if(configHash()!==q.liveConfigurationSha256)throw Error('Configuration changed during final images');PasteWastePrime.compareExact(snapshot().raw,q.finalTargetRaw,'batch final pose');
  if(q.mode==='wet'){ledger=CommissioningStroke.finishBatch(ledger,q,true);var completedLedgerBytes=bytes(JSON.stringify(ledger,null,2)+'\n');Fs.write(ledgerFile.toPath(),completedLedgerBytes);if(hash(Fs.readAllBytes(ledgerFile.toPath()))!==hash(completedLedgerBytes))throw Error('Completed ledger write not verified');r.completedLedgerSha256=hash(completedLedgerBytes);}else if(hash(Fs.readAllBytes(ledgerFile.toPath()))!==q.previousLedgerSha256)throw Error('Air batch observed ledger changed');
  r.uncertainCompletion=false;r.observationRequiredBeforeNextIncrement=true;r.flowCalibrated=false;r.deliveredVolumeMeasured=false;r.finishedAt=new Date().toISOString();save(q.mode==='wet'?'completed-contiguous-batch-awaiting-observation':'completed-contiguous-air-batch-awaiting-observation');
 }catch(e){
  if(q.mode==='wet'&&ledger!==null){try{ledger=CommissioningStroke.finishBatch(ledger,q,false);Fs.write(ledgerFile.toPath(),bytes(JSON.stringify(ledger,null,2)+'\n'));}catch(ledgerError){r.ledgerError=String(ledgerError);}}
  r.error=String(e);r.uncertainCompletion=(r.motionSubmitted&&!r.controllerPositionVerified)||r.transportUncertain===true;r.auditIncomplete=true;r.finishedAt=new Date().toISOString();
  if(r.motionSubmitted||r.controllerQuerySubmitted){
   keepBusy=true;r.queuedTasksCancelled=0;var pending;
   while((pending=executor.getQueue().poll())!=null){if(pending instanceof Java.type('java.util.concurrent.Future'))pending.cancel(false);r.queuedTasksCancelled++;}
   executor.shutdown();r.executorQuarantined=true;
   r.faultGateScope='Retained busy marker and stopped current executor block reviewed dispatcher/busy-sensitive UI only; arbitrary direct native submission may recreate an executor. Operator physical stop/recovery required; no autonomous retry.';
  }
  save(r.cooperativeStopRequested?'stopped-contiguous-batch-no-retry':'failed-no-retry-no-recovery-motion');
 }finally{
  if(ownedTask&&!keepBusy){taskOwner(null);m.fireMachineBusy(false);}
  print(String(out));
 }
 return null;
 }}));}catch(queueError){r.error=String(queueError);r.uncertainCompletion=false;save('enqueue-failed-no-motion');throw queueError;}
})();
