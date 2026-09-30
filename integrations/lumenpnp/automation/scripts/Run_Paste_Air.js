// STAGED REPLACEMENT: not commissioned. No raw fork G-code or serial connection.
// False until calibrated native path/session and independent activation review.
var PASTE_PHYSICAL_EXECUTION_ENABLED = false;
(function(){
 if(!PASTE_PHYSICAL_EXECUTION_ENABLED)throw Error('Paste physical execution disabled; measured native path and transport activation review required');
 var C=Java.type('org.openpnp.model.Configuration'),F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8,
 MD=Java.type('java.security.MessageDigest'),MM=Java.type('org.openpnp.model.LengthUnit').Millimeters,AL=Java.type('org.openpnp.model.AxesLocation'),
 L=Java.type('org.openpnp.model.Location'),MO=Java.type('org.openpnp.model.Motion$MotionOption'),CT=Java.type('org.openpnp.machine.reference.driver.GcodeDriver$CommandType'),I=Java.type('javax.imageio.ImageIO');
 var root='/home/lumen/lumenpnp/',m=C.get().getMachine(),planner=m.getMotionPlanner();
 function read(p){return String(new java.lang.String(Fs.readAllBytes(new F(p).toPath()),UTF));}
 function hash(bytes){var a=MD.getInstance('SHA-256').digest(bytes),s='';for(var i=0;i<a.length;i++)s+=('0'+((a[i]&255).toString(16))).slice(-2);return s;}
 function bytes(s){return new java.lang.String(s).getBytes(UTF);}
 function privateValue(className,name,obj){var f=Java.type(className).class.getDeclaredField(name);f.setAccessible(true);return f.get(obj);}
 function configHash(){var w=new java.io.StringWriter();C.createSerializer().write(m,w);return hash(bytes(String(w)));}
 eval(read(root+'automation/paste/survey-request.cjs'));
 eval(read(root+'automation/paste/connection-policy.cjs'));
 eval(read(root+'automation/paste/safety.cjs'));
 eval(read(root+'automation/paste/native-air.cjs'));
 var planText=read(root+'automation/plans/paste-air-plan.json'),plan=JSON.parse(planText),session=JSON.parse(read(root+'automation/plans/paste-session.json')),
 jvm=Number(Java.type('java.lang.management.ManagementFactory').getRuntimeMXBean().getStartTime()),planHash=hash(bytes(planText));
 PasteSafety.session(session,plan,planHash,Number(java.lang.System.currentTimeMillis()),jvm);
 var q=NativePasteAir.session(session,Number(java.lang.System.currentTimeMillis()));
 var corridor=new F(q.clearanceEvidence.path);if(!corridor.isFile()||hash(Fs.readAllBytes(corridor.toPath()))!==q.clearanceEvidence.sha256)throw Error('Reviewed swept-clearance image missing/changed');
 var panel=Java.type('org.openpnp.gui.MainFrame').get().getJobTab(),state=panel.getClass().getDeclaredField('state');state.setAccessible(true);
 if(m.getDrivers().size()!==1)throw Error('Unexpected driver topology');var d=m.getDrivers().get(0);
 if(String(d.getClass().getName())!=='org.openpnp.machine.reference.driver.GcodeDriver'||String(d.getId())!=='DRV16982438146c1dd4')throw Error('Unknown driver');
 if(String(planner.getClass().getName())!=='org.openpnp.machine.reference.driver.NullMotionPlanner')throw Error('Only audited NullMotionPlanner allowed');
 var nativePositionAckTimeout=Number(privateValue('org.openpnp.machine.reference.driver.GcodeDriver','infinityTimeoutMilliseconds',d));if(!isFinite(nativePositionAckTimeout)||nativePositionAckTimeout<=0||nativePositionAckTimeout>60000)throw Error('Unbounded/unreviewed native position ACK timeout');
 var jar=new F(d.getClass().getProtectionDomain().getCodeSource().getLocation().toURI());if(hash(Fs.readAllBytes(jar.toPath()))!=='bcd34923ae91d61a96b98b4c82c93cdc90093ff94292270fd0a18fc6f96f7752')throw Error('Installed native API binary changed');
 var head=m.getDefaultHead(),left=head.getNozzleByName('N1'),right=head.getNozzleByName('N2'),top=head.getDefaultCamera(),bottom=null;
 for each(var camera in m.getCameras())if(String(camera.getLooking())==='Up'){if(bottom!==null)throw Error('Multiple bottom cameras');bottom=camera;}
 if(left==null||right==null||top==null||bottom==null||String(left.getId())!=='N1'||String(top.getId())!=='CAM1607555396816'||String(top.getLooking())!=='Down'||String(right.getId())!=='NOZ1710829fd33a0170')throw Error('Unexpected nozzles/cameras');
 if(String(left.getId())!==plan.profile.leftNozzleId||String(right.getId())!==plan.profile.rightNozzleId||left.getHead()!==right.getHead())throw Error('Measured nozzle/head topology changed');
 if(String(left.getHeadOffsets())!==plan.profile.leftHeadOffsets||String(right.getHeadOffsets())!==plan.profile.rightHeadOffsets)throw Error('Measured head offsets changed');
 var items={N1:left,N2:right,top:top,bottom:bottom};
 function pose(n){var p=n.getLocation().convertToUnits(MM);return {x:Number(p.getX()),y:Number(p.getY()),z:Number(p.getZ()),rotation:Number(p.getRotation())};}
 function poses(){var a={};Object.keys(items).forEach(function(k){a[k]=pose(items[k]);});return a;}
 function comparePoses(a,b){Object.keys(items).forEach(function(k){['x','y','z','rotation'].forEach(function(axis){PasteSurveyRequest.close(a[k][axis],b[k][axis],0.0001,k+' pose '+axis);});});}
 var axes={},ids={X:'AXS169824381580efcb',Y:'AXS16982438158c4660',Z:'AXS16982438158d0458',A:'AXS16b068df4e35374e',B:'AXS17108288e61da5fb'};
 for each(var a in new AL(m).drivenBy(d).getControllerAxes()){var letter=String(a.getLetter());if(!ids[letter]||String(a.getId())!==ids[letter]||axes[letter])throw Error('Unexpected raw axis');axes[letter]=a;}
 if(Object.keys(axes).sort().join(',')!=='A,B,X,Y,Z')throw Error('Missing raw axis');
 function snapshot(){var s={raw:{},driver:{},nativePoses:poses()};Object.keys(axes).forEach(function(k){s.raw[k]=Number(axes[k].getCoordinate());s.driver[k]=Number(axes[k].getDriverCoordinate());});return s;}
 function stateGate(){
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
  ['X','Y'].forEach(function(k){if(['None','OneSidedPositioning'].indexOf(String(axes[k].getBacklashCompensationMethod()))<0)throw Error('Unaudited XY backlash method');});
  if(Number(planner.getMinimumSpeed())!==0.05)throw Error('Audited native minimum speed changed');
  var completeRegex=d.getCommand(top,CT.MOVE_TO_COMPLETE_REGEX);if(completeRegex!=null&&String(completeRegex).trim())throw Error('Native completion regex could hide responses');
  if(String(d.getCommand(null,CT.COMMAND_CONFIRM_REGEX)).trim()!=='^ok.*')throw Error('Native ACK regex changed');
  if(String(d.getCommand(null,CT.COMMAND_ERROR_REGEX))!==NativePasteAir.nativeErrorRegex)throw Error('Native per-line error/reset latch absent or unaudited; activation blocked');
  var moveTemplate=PasteConnectionPolicy.tokens(d.getCommand(top,CT.MOVE_TO_COMMAND));
  if(JSON.stringify(moveTemplate)!==JSON.stringify(['{Acceleration:M204 S%.0f }','G1 {X:X%.4f} {Y:Y%.4f} {Z:Z%.4f} {A:A%.4f} {B:B%.4f} {FeedRate:F%.0f}']))throw Error('Native motion template changed');
  if(['M114','M114 ; get position'].indexOf(String(d.getCommand(null,CT.GET_POSITION_COMMAND)).trim())<0)throw Error('Position query command changed');
  if(JSON.stringify(PasteConnectionPolicy.tokens(d.getCommand(top,CT.MOVE_TO_COMPLETE_COMMAND)))!==JSON.stringify(['M400']))throw Error('Motion completion command changed');
 }
 stateGate();if(configHash()!==plan.profile.liveConfigurationSha256)throw Error('Live configuration changed');
 var executor=privateValue('org.openpnp.spi.base.AbstractMachine','executor',m);
 if(executor==null||executor.isShutdown()||executor.isTerminated()||executor.getCorePoolSize()!==1||executor.getMaximumPoolSize()!==1||executor.getActiveCount()!==0||!executor.getQueue().isEmpty())throw Error('Existing native single-worker executor must be idle; no second executor is created');
 var taskSetter=Java.type('org.openpnp.spi.base.AbstractMachine').class.getDeclaredMethod('setTaskThread',Java.type('java.lang.Thread').class);taskSetter.setAccessible(true);
 function taskOwner(thread){taskSetter.invoke(m,Java.to([thread],'java.lang.Object[]'));}
 function settle(){var delay=Math.max(200,Number(top.getSettleTimeMs()),Number(bottom.getSettleTimeMs()));if(!isFinite(delay)||delay>3000)throw Error('Unreviewed camera settle interval');java.lang.Thread.sleep(Math.ceil(delay));}
 var initial=snapshot();PasteSurveyRequest.compareExact(initial.raw,q.expectedRaw,'expected raw');PasteSurveyRequest.compareExact(initial.driver,q.expectedDriver,'expected driver');comparePoses(initial.nativePoses,q.expectedNativePoses);
 ['x','y','z','rotation'].forEach(function(k){PasteSurveyRequest.close(initial.nativePoses.N1[k],session.start.left[k],0.0001,'left calibrated start '+k);PasteSurveyRequest.close(initial.nativePoses.N2[k],session.start.right[k],0.0001,'right calibrated start '+k);});
 var nativeStart=right.getLocation().convertToUnits(MM),rawTargets=[];
 function cloneRaw(p){var a={};Object.keys(axes).forEach(function(k){a[k]=p[k];});return a;}
 plan.points.forEach(function(point){var location=new L(MM,point.x,point.y,nativeStart.getZ(),nativeStart.getRotation());if(!right.isReachable(location))throw Error('Measured native target unreachable');
  var raw=right.toRaw(right.toHeadLocation(location)),target=cloneRaw(initial.raw),mapped=[];
  for each(var axis in raw.getControllerAxes()){var k=String(axis.getLetter());if(axes[k]!==axis)throw Error('Unrecognized native transform axis');mapped.push(k);var v=Number(raw.getCoordinate(axis));if(k==='X'||k==='Y')target[k]=v;else PasteSurveyRequest.close(v,initial.raw[k],0.0000001,'unchanged transform '+k);}
  if(mapped.sort().join(',')!=='B,X,Y,Z')throw Error('N2 native transform mapping changed');rawTargets.push(target);
 });
 var spec={startRaw:initial.raw,targets:rawTargets,axisOrder:q.axisOrder,speedFraction:plan.profile.speedFraction,minimumSpeed:Number(planner.getMinimumSpeed()),maxSegmentMm:q.maxSegmentMm};
 var path=NativePasteAir.segments(spec),pathHash=hash(bytes(JSON.stringify(path)));
 if(pathHash!==q.rawSegmentsSha256)throw Error('Exact native L-shaped/split path was not reviewed');
 var out=new F(root+'automation/evidence/paste-air-'+plan.id);if(!out.mkdir())throw Error('Air plan already claimed; no retry');
 var r={schema:1,id:plan.id,mode:'air',status:'claimed',startedAt:new Date().toISOString(),plan:plan,session:session,beforeQuerySnapshot:initial,
 rawPath:path,rawPathSha256:pathHash,nativeMinimumSpeed:Number(planner.getMinimumSpeed()),transitions:[],motionSubmitted:false,positionQueryAckTimeoutMs:nativePositionAckTimeout,positionReportPollTimeoutMs:3000,physicalAcceptanceEstablished:false,calibrationEstablished:false,noReplay:true};
 function save(status){r.status=status;r.transitions.push({status:status,time:new Date().toISOString()});Fs.write(new F(out,'report.json').toPath(),bytes(JSON.stringify(r,null,2)+'\n'));}
 save('preflight-before-any-controller-query');
 var lastReported=null;
 var positionRegex='^.*X:(?<X>-?\\d+\\.\\d+)\\s*Y:(?<Y>-?\\d+\\.\\d+)\\s*Z:(?<Z>-?\\d+\\.\\d+)\\s*A:(?<A>-?\\d+\\.\\d+)\\s*B:(?<B>-?\\d+\\.\\d+).*';
 if(String(d.getCommand(null,CT.POSITION_REPORT_REGEX))!==positionRegex)throw Error('Audited position-report delimiter changed');
 var positionPattern=java.util.regex.Pattern.compile(positionRegex);
 function query(saved,label){
  var entry={saved:saved,responses:[]};r[label]=entry;
  // Inspect pending motion/M400 responses before sending the read-only query.
  append(d.receiveResponses(),entry.responses);checkedLines(entry.responses);
  if(entry.responses.some(function(line){return positionPattern.matcher(line).matches();}))throw Error('Stale position response before fresh query');
  r.transportUncertain=true;r.controllerQuerySubmitted=true;save(label+'-query-started');
  var observed=d.getReportedLocation(3000),reported={};for each(var a in observed.getControllerAxes())reported[String(a.getLetter())]=Number(observed.getCoordinate(a));
  collect(positionRegex,entry);
  var delimiter=-1;entry.responses.forEach(function(line,i){if(positionPattern.matcher(line).matches())delimiter=i;});
  if(delimiter<0)throw Error('Fresh M114 delimiter missing');
  var ackAfter=entry.responses.slice(delimiter+1).some(function(line){return /^ok/.test(line);});
  if(!ackAfter)collect('^ok.*',entry);
  append(d.receiveResponses(),entry.responses);checkedLines(entry.responses);
  entry.reported=reported;save(label+'-reported');PasteSurveyRequest.compareReported(reported,saved.raw,saved.driver);r.transportUncertain=false;lastReported=reported;return reported;
 }
 function capture(camera,name){
  if(String(camera.getClass().getName())!=='org.openpnp.machine.reference.camera.OpenPnpCaptureCamera')throw Error('Unknown camera capture implementation');
  var open=camera.getClass().getDeclaredMethod('isOpen');open.setAccessible(true);if(!open.invoke(camera))throw Error('Camera stream not already open; no reopen');
  var image=camera.captureRaw();if(image==null||!I.write(image,'png',new F(out,name+'.png')))throw Error('Raw capture failed');return {image:image,path:name+'.png',width:image.getWidth(),height:image.getHeight()};
 }
 function append(javaLines,target){for each(var line in javaLines)target.push(String(line.getLine()));}
 function checkedLines(lines){PasteConnectionPolicy.responses(lines);lines.forEach(function(line){if(/unknown command|halted|fatal|\bkilled\b/i.test(line))throw Error('Controller fault: '+line);});}
 function collect(regex,entry){var list=d.receiveResponses(regex,3000,new (Java.type('org.openpnp.machine.reference.driver.GcodeDriver$TimeoutAction'))({apply:function(lines){append(lines,entry.responses);checkedLines(entry.responses);save('response-timeout');throw new java.lang.Exception('Native air response timeout; no retry');}}));append(list,entry.responses);checkedLines(entry.responses);}
 function control(){var f=new F(root+'automation/plans/paste-control.json');if(!f.exists())return null;var c=JSON.parse(read(String(f)));if(c.planId!==plan.id||(c.action!=='pause'&&c.action!=='cancel'))throw Error('Invalid/stale air control');return c.action;}
 function context(){PasteSafety.session(session,plan,planHash,Number(java.lang.System.currentTimeMillis()),jvm);NativePasteAir.session(session,Number(java.lang.System.currentTimeMillis()));stateGate();if(!executor.getQueue().isEmpty())throw Error('Competing native work queued');return {enabled:true,homed:true,jobStopped:true,emptyHeads:true,quarantined:true,ownedTask:m.isTask(java.lang.Thread.currentThread()),plannerEmpty:true,driverNotPending:true,subordinateEmpty:true,completionRegexAbsent:true,minimumSpeed:Number(planner.getMinimumSpeed())};}
 function checkBounds(raw){['X','Y'].forEach(function(k){var limits=plan.profile.rawBounds[String(axes[k].getId())];if(!limits)throw Error('Missing measured raw '+k+' bounds');PasteSafety.bound(raw[k],limits.min,limits.max,'raw '+k);});}
 function clearancePose(saved){['N1','N2','top','bottom'].forEach(function(k){['z','rotation'].forEach(function(a){PasteSurveyRequest.close(saved.nativePoses[k][a],initial.nativePoses[k][a],a==='rotation'?0.3:0.02,'joint-clearance '+k+' '+a);});});}
 save('queued-on-existing-native-executor');
 try{executor.submit(new (Java.type('java.util.concurrent.Callable'))({call:function(){
 var ownedTask=false,keepBusy=false,claimedInTask=false,expected=cloneRaw(initial.raw),beforeStep=null,segmentIndex=0;
 try{
  if(m.isBusy()||!executor.getQueue().isEmpty())throw Error('Native task ownership changed before air run');
  taskOwner(java.lang.Thread.currentThread());ownedTask=true;m.fireMachineBusy(true);
  PasteSafety.session(session,plan,planHash,Number(java.lang.System.currentTimeMillis()),jvm);NativePasteAir.session(session,Number(java.lang.System.currentTimeMillis()));stateGate();
  if(configHash()!==plan.profile.liveConfigurationSha256)throw Error('Measured configuration changed');
  var taskStart=snapshot();PasteSurveyRequest.compareExact(taskStart.raw,initial.raw,'queued raw');PasteSurveyRequest.compareExact(taskStart.driver,initial.driver,'queued driver');comparePoses(taskStart.nativePoses,initial.nativePoses);
  r.result=NativePasteAir.run(spec,{
   claim:function(){if(claimedInTask)throw Error('Task claim reused');claimedInTask=true;},state:context,
   preflight:function(segments){checkBounds(initial.raw);segments.forEach(function(segment){checkBounds(segment.to);if(segment.axis!==null){var partial=new AL(axes[segment.axis],segment.to[segment.axis]);if(partial.getControllerAxes().size()!==1||!partial.contains(axes[segment.axis])||!planner.isValidLocation(top,partial))throw Error('Partial native target invalid');}});if(hash(bytes(JSON.stringify(segments)))!==q.rawSegmentsSha256)throw Error('Reviewed path changed');},
   boundary:function(start){query(snapshot(),'before');PasteSurveyRequest.compareReported(lastReported,start,initial.driver);settle();var a=capture(top,'top-before-raw'),b=capture(bottom,'bottom-before-raw');r.beforeImages={top:a.path,bottom:b.path};},
   control:control,record:function(status,state){r.progress=JSON.parse(JSON.stringify(state));save(status);},
   move:function(segment){
    context();if(configHash()!==plan.profile.liveConfigurationSha256)throw Error('Configuration changed during air path');
    var saved=snapshot();PasteSurveyRequest.comparePostModel(saved.raw,segment.from);clearancePose(saved);PasteSurveyRequest.compareReported(lastReported,saved.raw,saved.driver);beforeStep=cloneRaw(lastReported);
    var partial=new AL(axes[segment.axis],segment.to[segment.axis]);if(partial.getControllerAxes().size()!==1||!partial.contains(axes[segment.axis]))throw Error('Air move must contain exactly one selected raw XY axis');
    r.motionSubmitted=true;r.nativeMotionCompletionReported=false;r.controllerPositionVerified=false;save('submitting-single-axis-native-motion');
    planner.moveTo(top,partial,plan.profile.speedFraction,MO.SpeedOverPrecision);
    r.nativeMotionCompletionReported=true;save('native-stillstand-reported');
   },
   verify:function(segment){var saved=snapshot();PasteSurveyRequest.comparePostModel(saved.raw,segment.to);clearancePose(saved);var actual=query(saved,'segment-'+segmentIndex);NativePasteAir.verifyStep(beforeStep,actual,segment);expected=cloneRaw(segment.to);r.controllerPositionVerified=true;segmentIndex++;},
   fault:function(error,state){r.progress=JSON.parse(JSON.stringify(state));r.error=String(error);}
  });
  var after=snapshot();r.afterQuerySnapshot=after;PasteSurveyRequest.comparePostModel(after.raw,expected);clearancePose(after);
  settle();var afterTop=capture(top,'top-after-raw'),afterBottom=capture(bottom,'bottom-after-raw');r.afterImages={top:afterTop.path,bottom:afterBottom.path};
  r.uncertainCompletion=false;r.finishedAt=new Date().toISOString();save(r.result.stop?(r.result.stop==='pause'?'paused-at-clearance-new-plan-required':'cancelled-at-clearance'):'completed-air-software');
 }catch(e){
  r.error=String(e);r.uncertainCompletion=!!r.transportUncertain||(r.motionSubmitted&&!r.controllerPositionVerified);r.auditIncomplete=true;r.finishedAt=new Date().toISOString();
  if(r.motionSubmitted||r.controllerQuerySubmitted){
   keepBusy=true;r.queuedTasksCancelled=0;var pending;
   while((pending=executor.getQueue().poll())!=null){if(pending instanceof Java.type('java.util.concurrent.Future'))pending.cancel(false);r.queuedTasksCancelled++;}
   executor.shutdown();r.executorQuarantined=true;
   r.faultGateScope='Retained busy marker and stopped current executor block reviewed dispatcher/busy-sensitive UI only; arbitrary direct native submission may recreate an executor. Operator physical stop/recovery required; no autonomous retry.';
  }
  save('fault-no-recovery-motion');
 }finally{
  if(ownedTask&&!keepBusy){taskOwner(null);m.fireMachineBusy(false);}
  print(String(out));
 }
 return null;
 }}));}catch(queueError){r.error=String(queueError);r.uncertainCompletion=false;save('enqueue-failed-no-motion');throw queueError;}
})();
