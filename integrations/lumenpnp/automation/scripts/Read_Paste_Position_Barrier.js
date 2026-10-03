// Native M114 barrier; optional explicitly acknowledged M400 completion of prior manual jog only. No new motion, actuation or connection.
(function(){
 var C=Java.type('org.openpnp.model.Configuration'),F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8,
 MD=Java.type('java.security.MessageDigest'),MM=Java.type('org.openpnp.model.LengthUnit').Millimeters,AL=Java.type('org.openpnp.model.AxesLocation'),
 MO=Java.type('org.openpnp.model.Motion$MotionOption'),CT=Java.type('org.openpnp.machine.reference.driver.GcodeDriver$CommandType'),I=Java.type('javax.imageio.ImageIO');
 var root='/home/lumen/lumenpnp/',m=C.get().getMachine(),planner=m.getMotionPlanner();
 function read(p){return String(new java.lang.String(Fs.readAllBytes(new F(p).toPath()),UTF));}
 function hash(bytes){var a=MD.getInstance('SHA-256').digest(bytes),s='';for(var i=0;i<a.length;i++)s+=('0'+((a[i]&255).toString(16))).slice(-2);return s;}
 function bytes(s){return new java.lang.String(s).getBytes(UTF);}
 function privateValue(className,name,obj){var f=Java.type(className).class.getDeclaredField(name);f.setAccessible(true);return f.get(obj);}
 function configHash(){var w=new java.io.StringWriter();C.createSerializer().write(m,w);return hash(bytes(String(w)));}
 eval(read(root+'automation/paste/survey-request.cjs'));
 eval(read(root+'automation/paste/position-barrier.cjs'));
 eval(read(root+'automation/paste/native-air.cjs'));
 eval(read(root+'automation/paste/connection-policy.cjs'));
 var q=JSON.parse(read(root+'automation/plans/paste-position-barrier-request.json')),jvm=Number(Java.type('java.lang.management.ManagementFactory').getRuntimeMXBean().getStartTime());
 PastePositionBarrier.validate(q,Number(java.lang.System.currentTimeMillis()),jvm);
 var installFile=new F(q.installerEvidence.path);if(!installFile.isFile())throw Error('Installer evidence missing');var installBytes=Fs.readAllBytes(installFile.toPath());if(hash(installBytes)!==q.installerEvidence.sha256)throw Error('Installer evidence changed');var installation=JSON.parse(String(new java.lang.String(installBytes,UTF)));var installerRequest=q;
 if(installation.scope!=='pure-model-state-no-controller-access'&&installation.status!=='completed-native-home-enabled-awaiting-image-review'&&installation.liveConfigurationAfterSha256!==q.liveConfigurationSha256){
  var lineage=q.calibrationXmlEvidence;if(!lineage)throw Error('Explicit calibration XML lineage required');
  function checkedXml(e,expected){if(!e||e.sha256!==expected||typeof e.path!=='string'||e.path.charAt(0)!=='/')throw Error('Exact calibration XML hash required');var data=Fs.readAllBytes(new F(e.path).toPath());if(hash(data)!==expected)throw Error('Calibration XML changed');return String(new java.lang.String(data,UTF));}
  PastePositionBarrier.calibrationXml(checkedXml(lineage.before,installation.liveConfigurationAfterSha256),checkedXml(lineage.after,q.liveConfigurationSha256));
  installerRequest={};Object.keys(q).forEach(function(k){installerRequest[k]=q[k];});installerRequest.liveConfigurationSha256=installation.liveConfigurationAfterSha256;
 }
 PastePositionBarrier.installer(installation,installerRequest);if(installation.scope!=='pure-model-state-no-controller-access'&&installation.status!=='completed-native-home-enabled-awaiting-image-review'&&installation.installedRegex!==NativePasteAir.nativeErrorRegex)throw Error('Installer pattern differs');
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
 function comparePoses(a,b){Object.keys(items).forEach(function(k){['x','y','z','rotation'].forEach(function(axis){PasteSurveyRequest.close(a[k][axis],b[k][axis],0.0001,k+' pose '+axis);});});}
 var axes={},ids={X:'AXS169824381580efcb',Y:'AXS16982438158c4660',Z:'AXS16982438158d0458',A:'AXS16b068df4e35374e',B:'AXS17108288e61da5fb'};
 for each(var a in new AL(m).drivenBy(d).getControllerAxes()){var letter=String(a.getLetter());if(!ids[letter]||String(a.getId())!==ids[letter]||axes[letter])throw Error('Unexpected raw axis');axes[letter]=a;}
 if(Object.keys(axes).sort().join(',')!=='A,B,X,Y,Z')throw Error('Missing raw axis');
 function snapshot(){var s={raw:{},driver:{},nativePoses:poses()};Object.keys(axes).forEach(function(k){s.raw[k]=Number(axes[k].getCoordinate());s.driver[k]=Number(axes[k].getDriverCoordinate());});return s;}
 var originalReader=privateValue('org.openpnp.machine.reference.driver.GcodeDriver','readerThread',d),originalCommands=d.commands;
 function stateGate(allowPriorManualPending){
  if(d.commands!==originalCommands||originalReader==null||!originalReader.isAlive()||privateValue('org.openpnp.machine.reference.driver.GcodeDriver','readerThread',d)!==originalReader||privateValue('org.openpnp.machine.reference.driver.GcodeDriver','errorResponse',d)!=null)throw Error('Reader/commands changed or prior native error');
  if((m.isBusy()&&!m.isTask(java.lang.Thread.currentThread()))||String(state.get(panel))!=='Stopped')throw Error('Need idle machine, stopped job');
  if(String(privateValue('org.openpnp.machine.reference.driver.GcodeDriver','connected',d))!=='true'||(d.isMotionPending()&&!(allowPriorManualPending===true&&q.manualJogCompletionAcknowledgement===true)))throw Error('Driver disconnected or prior motion pending');
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
  var completeRegex=d.getCommand(top,CT.MOVE_TO_COMPLETE_REGEX);if(completeRegex!=null&&String(completeRegex).trim())throw Error('Native completion regex could hide responses');
  if(String(d.getCommand(null,CT.COMMAND_CONFIRM_REGEX)).trim()!=='^ok.*')throw Error('Native ACK regex changed');
  if(String(d.getCommand(null,CT.COMMAND_ERROR_REGEX))!==NativePasteAir.nativeErrorRegex)throw Error('Native per-line error/reset latch absent or unaudited; activation blocked');
  var moveTemplate=PasteConnectionPolicy.tokens(d.getCommand(top,CT.MOVE_TO_COMMAND));
  if(JSON.stringify(moveTemplate)!==JSON.stringify(['{Acceleration:M204 S%.0f }','G1 {X:X%.4f} {Y:Y%.4f} {Z:Z%.4f} {A:A%.4f} {B:B%.4f} {FeedRate:F%.0f}']))throw Error('Native motion template changed');
  if(['M114','M114 ; get position'].indexOf(String(d.getCommand(null,CT.GET_POSITION_COMMAND)).trim())<0)throw Error('Position query command changed');
  if(JSON.stringify(PasteConnectionPolicy.tokens(d.getCommand(top,CT.MOVE_TO_COMPLETE_COMMAND)))!==JSON.stringify(['M400']))throw Error('Motion completion command changed');
 }
 stateGate(q.manualJogCompletionAcknowledgement===true);if(configHash()!==q.liveConfigurationSha256)throw Error('Live configuration changed');
 var executor=privateValue('org.openpnp.spi.base.AbstractMachine','executor',m);
 if(executor==null||executor.isShutdown()||executor.isTerminated()||executor.getCorePoolSize()!==1||executor.getMaximumPoolSize()!==1||executor.getActiveCount()!==0||!executor.getQueue().isEmpty())throw Error('Existing native single-worker executor must be idle; no second executor is created');
 var taskSetter=Java.type('org.openpnp.spi.base.AbstractMachine').class.getDeclaredMethod('setTaskThread',Java.type('java.lang.Thread').class);taskSetter.setAccessible(true);
 function taskOwner(thread){taskSetter.invoke(m,Java.to([thread],'java.lang.Object[]'));}
 var initial=snapshot();PasteSurveyRequest.compareExact(initial.raw,q.expectedRaw,'expected raw');PasteSurveyRequest.compareExact(initial.driver,q.expectedDriver,'expected driver');comparePoses(initial.nativePoses,q.expectedNativePoses);
 var out=new F(root+'automation/evidence/paste-position-barrier-'+q.id);if(!out.mkdir())throw Error('Position barrier UUID already claimed; no retry');
 var privateRoot=new F(root+'.local-machine-backups');if(!privateRoot.isDirectory())throw Error('Private backup root missing');var privateOut=new F(privateRoot,'paste-position-barrier-'+q.id);if(!privateOut.mkdir())throw Error('Private barrier UUID already claimed');
 var r={schema:1,id:q.id,status:'claimed',startedAt:new Date().toISOString(),request:q,beforeQuerySnapshot:initial,transitions:[],motionSubmitted:false,positionQueryAckTimeoutMs:nativePositionAckTimeout,physicalAcceptanceEstablished:false,calibrationEstablished:false,noReplay:true};
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
 function append(javaLines,target){for each(var line in javaLines)target.push(String(line.getLine()));}
 function checkedLines(lines){PasteConnectionPolicy.responses(lines);lines.forEach(function(line){if(/unknown command|halted|fatal|\bkilled\b/i.test(line))throw Error('Controller fault: '+line);});}
 function collect(regex,entry){var list=d.receiveResponses(regex,3000,new (Java.type('org.openpnp.machine.reference.driver.GcodeDriver$TimeoutAction'))({apply:function(lines){append(lines,entry.responses);checkedLines(entry.responses);save('response-timeout');throw new java.lang.Exception('Native air response timeout; no retry');}}));append(list,entry.responses);checkedLines(entry.responses);}
 save('queued-on-existing-native-executor');
 try{executor.submit(new (Java.type('java.util.concurrent.Callable'))({call:function(){
 var ownedTask=false,keepBusy=false;
 try{
  if(m.isBusy()||!executor.getQueue().isEmpty())throw Error('Native task ownership changed before position query');
  taskOwner(java.lang.Thread.currentThread());ownedTask=true;m.fireMachineBusy(true);
  PastePositionBarrier.validate(q,Number(java.lang.System.currentTimeMillis()),jvm);stateGate(q.manualJogCompletionAcknowledgement===true);
  if(configHash()!==q.liveConfigurationSha256)throw Error('Configuration changed before native task');
  var taskStart=snapshot();PasteSurveyRequest.compareExact(taskStart.raw,initial.raw,'queued raw');PasteSurveyRequest.compareExact(taskStart.driver,initial.driver,'queued driver');comparePoses(taskStart.nativePoses,initial.nativePoses);
  if(q.manualJogCompletionAcknowledgement===true&&d.isMotionPending()){
   // Direct driver completion invokes only the already-validated M400 template;
   // never flush planner motion or clear pending flags by reflection.
   var completion={priorResponses:[],responses:[]};r.manualJogCompletion=completion;
   append(d.receiveResponses(),completion.priorResponses);checkedLines(completion.priorResponses);
   r.transportUncertain=true;r.completionOnlySubmitted=true;save('manual-jog-native-M400-submitted');
   d.waitForCompletion(top,Java.type('org.openpnp.spi.MotionPlanner$CompletionType').WaitForStillstand);
   append(d.receiveResponses(),completion.responses);checkedLines(completion.responses);
   if(!completion.responses.some(function(line){return /^ok/.test(line);}))collect('^ok.*',completion);
   if(d.isMotionPending())throw Error('Prior manual jog completion remained pending');
   var completedPose=snapshot();PasteSurveyRequest.compareExact(completedPose.raw,initial.raw,'completion unchanged raw');PasteSurveyRequest.compareExact(completedPose.driver,initial.driver,'completion unchanged driver');comparePoses(completedPose.nativePoses,initial.nativePoses);
   r.transportUncertain=false;r.manualJogCompletionVerified=true;save('manual-jog-native-M400-acknowledged');
  }
  stateGate();
  query(taskStart,'position');
  var after=snapshot();PasteSurveyRequest.compareExact(after.raw,initial.raw,'unchanged raw after position query');comparePoses(after.nativePoses,initial.nativePoses);PasteSurveyRequest.compareReported(r.position.reported,after.raw,after.driver);
  stateGate();if(!executor.getQueue().isEmpty()||configHash()!==q.liveConfigurationSha256)throw Error('State/configuration changed during position barrier');
  r.afterQuerySnapshot=after;r.reported=r.position.reported;r.controllerPositionVerified=true;
  var writer=new java.io.StringWriter();C.createSerializer().write(m,writer);var serialized=String(writer);r.liveConfigurationSha256=hash(bytes(serialized));var privateSnapshot=new F(privateOut,'live-machine-after.xml');Fs.write(privateSnapshot.toPath(),bytes(serialized));r.privateConfigurationSnapshot={path:String(privateSnapshot),sha256:r.liveConfigurationSha256};
  if(hash(Fs.readAllBytes(privateSnapshot.toPath()))!==q.liveConfigurationSha256)throw Error('Serialized post-query snapshot mismatch');
  r.noMotionCommandSubmitted=true;r.uncertainCompletion=false;r.finishedAt=new Date().toISOString();save('completed-read-only-position-barrier');
 }catch(e){
  r.error=String(e);r.uncertainCompletion=(r.motionSubmitted&&!r.controllerPositionVerified)||r.transportUncertain===true;r.auditIncomplete=true;r.finishedAt=new Date().toISOString();
  if(r.controllerQuerySubmitted||r.completionOnlySubmitted){
   keepBusy=true;r.queuedTasksCancelled=0;var pending;
   while((pending=executor.getQueue().poll())!=null){if(pending instanceof Java.type('java.util.concurrent.Future'))pending.cancel(false);r.queuedTasksCancelled++;}
   executor.shutdown();r.executorQuarantined=true;
   r.faultGateScope='Retained busy marker and stopped current executor block reviewed dispatcher/busy-sensitive UI only; arbitrary direct native submission may recreate an executor. Operator physical stop/recovery required; no autonomous retry.';
  }
  save('failed-no-retry-no-recovery-motion');
 }finally{
  if(ownedTask&&!keepBusy){taskOwner(null);m.fireMachineBusy(false);}
  print(String(out));
 }
 return null;
 }}));}catch(queueError){r.error=String(queueError);r.uncertainCompletion=false;save('enqueue-failed-no-motion');throw queueError;}
})();
