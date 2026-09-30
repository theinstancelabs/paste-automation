// REVIEWED NARROW signed raw Z observation; finer discrete choices separately staged.
var PASTE_Z_OBSERVATION_ENABLED = true;
var PASTE_FINE_Z_OBSERVATION_ENABLED = false;
// No serial ownership changes, safe-Z helper, rotation, pickup, vacuum or current.
// Uses the existing single-worker native executor with audited busy bookkeeping;
// bypasses the public wrapper whose completion/exception cleanup can flush motion.
(function(){
 if(!PASTE_Z_OBSERVATION_ENABLED)throw Error("Z observation disabled pending independent transport and physical review");
 var C=Java.type('org.openpnp.model.Configuration'),F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8,
 MD=Java.type('java.security.MessageDigest'),MM=Java.type('org.openpnp.model.LengthUnit').Millimeters,AL=Java.type('org.openpnp.model.AxesLocation'),
 MO=Java.type('org.openpnp.model.Motion$MotionOption'),CT=Java.type('org.openpnp.machine.reference.driver.GcodeDriver$CommandType'),I=Java.type('javax.imageio.ImageIO');
 var root='/home/lumen/lumenpnp/',m=C.get().getMachine(),planner=m.getMotionPlanner();
 function read(p){return String(new java.lang.String(Fs.readAllBytes(new F(p).toPath()),UTF));}
 function hash(bytes){var a=MD.getInstance('SHA-256').digest(bytes),s='';for(var i=0;i<a.length;i++)s+=('0'+((a[i]&255).toString(16))).slice(-2);return s;}
 function bytes(s){return new java.lang.String(s).getBytes(UTF);}
 function privateValue(className,name,obj){var f=Java.type(className).class.getDeclaredField(name);f.setAccessible(true);return f.get(obj);}
 function configHash(){var w=new java.io.StringWriter();C.createSerializer().write(m,w);return hash(bytes(String(w)));}
 eval(read(root+'automation/paste/z-observation.cjs'));
 eval(read(root+'automation/paste/native-air.cjs'));
 eval(read(root+'automation/paste/connection-policy.cjs'));
 var q=JSON.parse(read(root+'automation/plans/paste-z-observation-request.json')),jvm=Number(Java.type('java.lang.management.ManagementFactory').getRuntimeMXBean().getStartTime());
 PasteZObservation.validate(q,Number(java.lang.System.currentTimeMillis()),jvm);
 PasteZObservation.fineStepGate(q,PASTE_FINE_Z_OBSERVATION_ENABLED);
 var fineZ=Math.abs(q.deltaMm)<1,firmwareStepReview=null;
 if(fineZ){var settingsBytes=Fs.readAllBytes(new F(q.firmwareSettingsEvidence.path).toPath());if(hash(settingsBytes)!==q.firmwareSettingsEvidence.sha256)throw Error('Firmware settings evidence changed');firmwareStepReview=PasteZObservation.firmwareStepsEvidence(JSON.parse(String(new java.lang.String(settingsBytes,UTF))),q);}
 var corridor=new F(q.corridorEvidence.path);if(!corridor.isFile()||hash(Fs.readAllBytes(corridor.toPath()))!==q.corridorEvidence.sha256)throw Error('Reviewed corridor image missing/changed');
 var barrierFile=new F(q.barrierEvidence.path);if(!barrierFile.isFile())throw Error('Position barrier evidence missing');var barrierBytes=Fs.readAllBytes(barrierFile.toPath());if(hash(barrierBytes)!==q.barrierEvidence.sha256)throw Error('Position barrier evidence changed');var barrierRecord=JSON.parse(String(new java.lang.String(barrierBytes,UTF)));PasteZObservation.barrier(barrierRecord,q,Number(java.lang.System.currentTimeMillis()));
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
 function comparePoses(a,b){Object.keys(items).forEach(function(k){['x','y','z','rotation'].forEach(function(axis){PasteZObservation.close(a[k][axis],b[k][axis],0.0001,k+' pose '+axis);});});}
 var axes={},ids={X:'AXS169824381580efcb',Y:'AXS16982438158c4660',Z:'AXS16982438158d0458',A:'AXS16b068df4e35374e',B:'AXS17108288e61da5fb'};
 for each(var a in new AL(m).drivenBy(d).getControllerAxes()){var letter=String(a.getLetter());if(!ids[letter]||String(a.getId())!==ids[letter]||axes[letter])throw Error('Unexpected raw axis');axes[letter]=a;}
 if(Object.keys(axes).sort().join(',')!=='A,B,X,Y,Z')throw Error('Missing raw axis');
 function projectedPoses(raw){var result={};Object.keys(items).forEach(function(k){var n=items[k],location=n.getMappedAxes(m);Object.keys(axes).forEach(function(a){location=location.put(new AL(axes[a],raw[a]));});var p=n.toHeadMountableLocation(n.toTransformed(location)).convertToUnits(MM);result[k]={x:Number(p.getX()),y:Number(p.getY()),z:Number(p.getZ()),rotation:Number(p.getRotation())};});return result;}
 function snapshot(){var s={raw:{},driver:{},nativePoses:poses()};Object.keys(axes).forEach(function(k){s.raw[k]=Number(axes[k].getCoordinate());s.driver[k]=Number(axes[k].getDriverCoordinate());});return s;}
 var originalReader=privateValue('org.openpnp.machine.reference.driver.GcodeDriver','readerThread',d),originalCommands=d.commands;
 function nativeZConfiguration(){return {softLowEnabled:!!axes.Z.isSoftLimitLowEnabled(),softLowMm:Number(axes.Z.getSoftLimitLow().convertToUnits(MM).getValue()),softHighEnabled:!!axes.Z.isSoftLimitHighEnabled(),softHighMm:Number(axes.Z.getSoftLimitHigh().convertToUnits(MM).getValue()),safeLowEnabled:!!axes.Z.isSafeZoneLowEnabled(),safeLowMm:Number(axes.Z.getSafeZoneLow().convertToUnits(MM).getValue()),safeHighEnabled:!!axes.Z.isSafeZoneHighEnabled(),safeHighMm:Number(axes.Z.getSafeZoneHigh().convertToUnits(MM).getValue())};}
 function stateGate(){
  PasteZObservation.nativeConfiguration(nativeZConfiguration(),q);
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
  if(String(axes.Z.getType())!=='Z'||String(axes.Z.getBacklashCompensationMethod())!=='DirectionalCompensation'||Number(axes.Z.getBacklashOffset().convertToUnits(MM).getValue())!==0||Number(axes.Z.getSneakUpOffset().convertToUnits(MM).getValue())!==0)throw Error('Raw Z mapping/backlash differs from audited zero compensation');
  if(Number(axes.Z.getFeedratePerSecond().convertToUnits(MM).getValue())!==200)throw Error('Audited raw Z feed limit changed');
  if(Number(planner.getMinimumSpeed())!==0.05)throw Error('Audited native minimum speed changed');
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
 var initial=snapshot();PasteZObservation.compareExact(initial.raw,q.expectedRaw,'expected raw');PasteZObservation.compareExact(initial.driver,q.expectedDriver,'expected driver');comparePoses(initial.nativePoses,q.expectedNativePoses);
 var out=new F(root+'automation/evidence/paste-z-observation-'+q.id);if(!out.mkdir())throw Error('Survey UUID already claimed; no retry');
 var r={schema:1,id:q.id,status:'claimed',startedAt:new Date().toISOString(),request:q,beforeQuerySnapshot:initial,transitions:[],motionSubmitted:false,positionQueryAckTimeoutMs:nativePositionAckTimeout,nativeMinimumSpeed:0.05,nativeZConfiguration:nativeZConfiguration(),physicalAcceptanceEstablished:false,calibrationEstablished:false,noReplay:true};
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
  entry.reported=reported;save(label+'-reported');PasteZObservation.compareReported(reported,saved.raw,saved.driver);r.transportUncertain=false;lastReported=reported;return reported;
 }
 function append(javaLines,target){for each(var line in javaLines)target.push(String(line.getLine()));}
 function checkedLines(lines){PasteConnectionPolicy.responses(lines);lines.forEach(function(line){if(/unknown command|halted|fatal|\bkilled\b/i.test(line))throw Error('Controller fault: '+line);});}
 function collect(regex,entry){var list=d.receiveResponses(regex,3000,new (Java.type('org.openpnp.machine.reference.driver.GcodeDriver$TimeoutAction'))({apply:function(lines){append(lines,entry.responses);checkedLines(entry.responses);save('response-timeout');throw new java.lang.Exception('Native air response timeout; no retry');}}));append(list,entry.responses);checkedLines(entry.responses);}
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
  if(m.isBusy()||!executor.getQueue().isEmpty())throw Error('Native task ownership changed before survey');
  taskOwner(java.lang.Thread.currentThread());ownedTask=true;m.fireMachineBusy(true);
  PasteZObservation.validate(q,Number(java.lang.System.currentTimeMillis()),jvm);PasteZObservation.barrier(barrierRecord,q,Number(java.lang.System.currentTimeMillis()));stateGate();
  if(configHash()!==q.liveConfigurationSha256)throw Error('Configuration changed before native task');
  var taskStart=snapshot();PasteZObservation.compareExact(taskStart.raw,initial.raw,'queued raw');PasteZObservation.compareExact(taskStart.driver,initial.driver,'queued driver');comparePoses(taskStart.nativePoses,initial.nativePoses);
  PasteZObservation.fineStepGate(q,PASTE_FINE_Z_OBSERVATION_ENABLED);
  query(initial,'before');PasteZObservation.compareExact(snapshot().raw,initial.raw,'post-query unchanged raw');
  if(fineZ){r.firmwareStepReview=firmwareStepReview;r.beforeControllerCounts=PasteZObservation.controllerCounts(r.before.responses);}
  settle();var beforeTop=capture(top,'top-before-raw'),beforeBottom=capture(bottom,'bottom-before-raw');r.beforeImages={top:{path:beforeTop.path,width:beforeTop.width,height:beforeTop.height},bottom:{path:beforeBottom.path,width:beforeBottom.width,height:beforeBottom.height}};save('before-images-captured');
  PasteZObservation.validate(q,Number(java.lang.System.currentTimeMillis()),jvm);PasteZObservation.barrier(barrierRecord,q,Number(java.lang.System.currentTimeMillis()));stateGate();if(configHash()!==q.liveConfigurationSha256)throw Error('Configuration changed during preflight');
  if(!executor.getQueue().isEmpty())throw Error('Competing native work queued during camera preflight');
  var preMove=snapshot();PasteZObservation.compareExact(preMove.raw,initial.raw,'unchanged pre-move raw');comparePoses(preMove.nativePoses,initial.nativePoses);PasteZObservation.compareReported(r.before.reported,preMove.raw,preMove.driver);
  var move=PasteZObservation.step(q),expected=PasteZObservation.target(initial.raw,q),selectedAxis=axes[move.axis],target=new AL(selectedAxis,expected[move.axis]);
  if(target.getControllerAxes().size()!==1||!target.contains(selectedAxis)||Math.abs(Number(target.getCoordinate(selectedAxis))-expected[move.axis])>1e-9)throw Error('Survey must command exactly one raw Z target');
  if(!planner.isValidLocation(top,target))throw Error('Native selected-axis target outside limits');
  var predictedStart=projectedPoses(initial.raw),predictedTarget=projectedPoses(expected);comparePoses(predictedStart,initial.nativePoses);PasteZObservation.compareNativeStep(predictedStart,predictedTarget,q,0.0001);r.preflightNativeTransform={start:predictedStart,target:predictedTarget};
  r.commandedControllerAxes=[move.axis];r.postmoveComparisonTolerance={linearMm:0.02,angularDegrees:0.3,meaning:'Firmware reporting precision, not permission to command other axes'};r.expectedAfterRaw=expected;r.preMoveSnapshot=preMove;r.motionSubmitted=true;save('submitting-one-native-'+move.axis+'-move');
  // Partial single-axis location leaves all other axes untouched. This per-move
  // option bypasses audited one-sided backlash overshoot, without config edits.
  planner.moveTo(top,target,0.05,MO.SpeedOverPrecision);
  r.nativeMotionCompletionReported=true;save('native-stillstand-reported');
  // Audited NullMotionPlanner has already waited for stillstand here. Do not
  // issue a second generic completion or any recovery/park/lift on failure.
  var after=snapshot();r.afterQuerySnapshot=after;PasteZObservation.comparePostModel(after.raw,expected);
  query(after,'after');PasteZObservation.compareReported(r.after.reported,expected,after.driver);
  PasteZObservation.compareFirmwareStep(r.before.reported,r.after.reported,q);r.independentFirmwareStepVerified=true;
  if(fineZ){r.afterControllerCounts=PasteZObservation.controllerCounts(r.after.responses);r.fineControllerStepVerification=PasteZObservation.compareControllerCounts(r.beforeControllerCounts,r.afterControllerCounts,q);}
  PasteZObservation.compareNativeStep(initial.nativePoses,after.nativePoses,q);
  r.controllerPositionVerified=true;save('controller-position-verified');settle();var afterTop=capture(top,'top-after-raw'),afterBottom=capture(bottom,'bottom-after-raw');r.afterImages={top:{path:afterTop.path,width:afterTop.width,height:afterTop.height},bottom:{path:afterBottom.path,width:afterBottom.width,height:afterBottom.height}};
  pair(beforeTop,afterTop,'top-before-after');pair(beforeBottom,afterBottom,'bottom-before-after');r.contactSheets=['top-before-after.png','bottom-before-after.png'];
  r.uncertainCompletion=false;r.finishedAt=new Date().toISOString();save('completed-Z-observation-awaiting-image-review');
 }catch(e){
  r.error=String(e);r.uncertainCompletion=(r.motionSubmitted&&!r.controllerPositionVerified)||r.transportUncertain===true;r.auditIncomplete=true;r.finishedAt=new Date().toISOString();
  if(r.motionSubmitted||r.controllerQuerySubmitted){
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
