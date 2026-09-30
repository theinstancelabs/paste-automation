// STAGED stationary camera LED restore through the existing driver boolean API.
var PASTE_CAMERA_LED_RESTORE_ENABLED = true;
// No motion, home, Z, rotation, pickup, motor-current or configuration changes.
// Uses the existing single-worker native executor with audited busy bookkeeping;
// bypasses the public wrapper whose completion/exception cleanup can flush motion.
(function(){
 if(!PASTE_CAMERA_LED_RESTORE_ENABLED)throw Error("Camera LED restore disabled pending independent review");
 var C=Java.type('org.openpnp.model.Configuration'),F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8,
 MD=Java.type('java.security.MessageDigest'),MM=Java.type('org.openpnp.model.LengthUnit').Millimeters,AL=Java.type('org.openpnp.model.AxesLocation'),
 CT=Java.type('org.openpnp.machine.reference.driver.GcodeDriver$CommandType'),I=Java.type('javax.imageio.ImageIO');
 var root='/home/lumen/lumenpnp/',m=C.get().getMachine(),planner=m.getMotionPlanner();
 function read(p){return String(new java.lang.String(Fs.readAllBytes(new F(p).toPath()),UTF));}
 function hash(bytes){var a=MD.getInstance('SHA-256').digest(bytes),s='';for(var i=0;i<a.length;i++)s+=('0'+((a[i]&255).toString(16))).slice(-2);return s;}
 function bytes(s){return new java.lang.String(s).getBytes(UTF);}
 function privateValue(className,name,obj){var f=Java.type(className).class.getDeclaredField(name);f.setAccessible(true);return f.get(obj);}
 function configHash(){var w=new java.io.StringWriter();C.createSerializer().write(m,w);return hash(bytes(String(w)));}
 eval(read(root+'automation/paste/survey-request.cjs'));
 eval(read(root+'automation/paste/connection-policy.cjs'));
 eval(read(root+'automation/paste/camera-led.cjs'));
 eval(read(root+'automation/paste/native-air.cjs'));
 var q=JSON.parse(read(root+'automation/plans/paste-camera-led-request.json')),jvm=Number(Java.type('java.lang.management.ManagementFactory').getRuntimeMXBean().getStartTime());
 PasteCameraLED.validate(q,Number(java.lang.System.currentTimeMillis()),jvm);
 function freeze(value){if(value&&typeof value==='object'){Object.keys(value).forEach(function(k){freeze(value[k]);});Object.freeze(value);}return value;}
 freeze(q);
 var panel=Java.type('org.openpnp.gui.MainFrame').get().getJobTab(),state=panel.getClass().getDeclaredField('state');state.setAccessible(true);
 if(m.getDrivers().size()!==1)throw Error('Unexpected driver topology');var d=m.getDrivers().get(0);
 if(String(d.getClass().getName())!=='org.openpnp.machine.reference.driver.GcodeDriver'||String(d.getId())!=='DRV16982438146c1dd4')throw Error('Unknown driver');
 if(String(planner.getClass().getName())!=='org.openpnp.machine.reference.driver.NullMotionPlanner')throw Error('Only audited NullMotionPlanner allowed');
 var nativePositionAckTimeout=Number(privateValue('org.openpnp.machine.reference.driver.GcodeDriver','infinityTimeoutMilliseconds',d));if(!isFinite(nativePositionAckTimeout)||nativePositionAckTimeout<=0||nativePositionAckTimeout>60000)throw Error('Unbounded/unreviewed native position ACK timeout');
 var nativeActuationTimeout=Number(d.getTimeoutMilliseconds());if(!isFinite(nativeActuationTimeout)||nativeActuationTimeout<=0||nativeActuationTimeout>60000)throw Error('Unreviewed LED ACK timeout');
 var jar=new F(d.getClass().getProtectionDomain().getCodeSource().getLocation().toURI());if(hash(Fs.readAllBytes(jar.toPath()))!=='bcd34923ae91d61a96b98b4c82c93cdc90093ff94292270fd0a18fc6f96f7752')throw Error('Installed native API binary changed');
 var head=m.getDefaultHead(),left=head.getNozzleByName('N1'),right=head.getNozzleByName('N2'),top=head.getDefaultCamera(),bottom=null;
 for each(var camera in m.getCameras())if(String(camera.getLooking())==='Up'){if(bottom!==null)throw Error('Multiple bottom cameras');bottom=camera;}
 if(left==null||right==null||top==null||bottom==null||String(left.getId())!=='N1'||String(top.getId())!=='CAM1607555396816'||String(top.getLooking())!=='Down'||String(right.getId())!=='NOZ1710829fd33a0170')throw Error('Unexpected nozzles/cameras');
 var led=m.getActuator('ACT1605385237291');if(led==null||String(led.getId())!=='ACT1605385237291'||led.getDriver()!==d)throw Error('Expected LED native owner required');
 var items={N1:left,N2:right,top:top,bottom:bottom};
 function pose(n){var p=n.getLocation().convertToUnits(MM);return {x:Number(p.getX()),y:Number(p.getY()),z:Number(p.getZ()),rotation:Number(p.getRotation())};}
 function poses(){var a={};Object.keys(items).forEach(function(k){a[k]=pose(items[k]);});return a;}
 function comparePoses(a,b){Object.keys(items).forEach(function(k){['x','y','z','rotation'].forEach(function(axis){PasteSurveyRequest.close(a[k][axis],b[k][axis],0.0001,k+' pose '+axis);});});}
 var axes={},ids={X:'AXS169824381580efcb',Y:'AXS16982438158c4660',Z:'AXS16982438158d0458',A:'AXS16b068df4e35374e',B:'AXS17108288e61da5fb'};
 for each(var a in new AL(m).drivenBy(d).getControllerAxes()){var letter=String(a.getLetter());if(!ids[letter]||String(a.getId())!==ids[letter]||axes[letter])throw Error('Unexpected raw axis');axes[letter]=a;}
 if(Object.keys(axes).sort().join(',')!=='A,B,X,Y,Z')throw Error('Missing raw axis');
 function snapshot(){var s={raw:{},driver:{},nativePoses:poses()};Object.keys(axes).forEach(function(k){s.raw[k]=Number(axes[k].getCoordinate());s.driver[k]=Number(axes[k].getDriverCoordinate());});return s;}
 var originalReader=privateValue('org.openpnp.machine.reference.driver.GcodeDriver','readerThread',d),originalCommands=d.commands;
 var positionRegex='^.*X:(?<X>-?\\d+\\.\\d+)\\s*Y:(?<Y>-?\\d+\\.\\d+)\\s*Z:(?<Z>-?\\d+\\.\\d+)\\s*A:(?<A>-?\\d+\\.\\d+)\\s*B:(?<B>-?\\d+\\.\\d+).*',positionPattern=java.util.regex.Pattern.compile(positionRegex);
 function stateGate(){
  PasteCameraLED.validate(q,Number(java.lang.System.currentTimeMillis()),jvm);
  if(d.isInSimulationMode())throw Error('Physical native driver required');
  if(executor!=null&&(privateValue('org.openpnp.spi.base.AbstractMachine','executor',m)!==executor||executor.isShutdown()||executor.isTerminated()||!executor.getQueue().isEmpty()))throw Error('Native executor identity/state changed');
  if(originalReader==null||!originalReader.isAlive()||privateValue('org.openpnp.machine.reference.driver.GcodeDriver','readerThread',d)!==originalReader||d.commands!==originalCommands||privateValue('org.openpnp.machine.reference.driver.GcodeDriver','errorResponse',d)!=null)throw Error('Native reader/commands changed or controller error');
  if(String(d.getCommand(null,CT.COMMAND_ERROR_REGEX))!==NativePasteAir.nativeErrorRegex||String(d.getCommand(null,CT.POSITION_REPORT_REGEX))!==positionRegex)throw Error('Native error/position response contract changed');
  var subordinate=privateValue('org.openpnp.machine.reference.driver.AbstractMotionPlanner','subordinateMotion',planner),subQueue=privateValue('org.openpnp.machine.reference.driver.AbstractMotionPlanner$SubordinateMotion','queue',subordinate);if(subQueue!=null&&!subQueue.isEmpty())throw Error('Queued subordinate motion');
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
  PasteCameraLED.commandContract(d.getCommand(led,CT.ACTUATE_BOOLEAN_COMMAND),d.getCommand(null,CT.COMMAND_CONFIRM_REGEX));
  if(['M114','M114 ; get position'].indexOf(String(d.getCommand(null,CT.GET_POSITION_COMMAND)).trim())<0)throw Error('Position query command changed');
  if(JSON.stringify(PasteConnectionPolicy.tokens(d.getCommand(top,CT.MOVE_TO_COMPLETE_COMMAND)))!==JSON.stringify(['M400']))throw Error('Motion completion command changed');
 }
 stateGate();if(configHash()!==q.liveConfigurationSha256)throw Error('Live configuration changed');
 var executor=privateValue('org.openpnp.spi.base.AbstractMachine','executor',m);
 if(executor==null||executor.isShutdown()||executor.isTerminated()||executor.getCorePoolSize()!==1||executor.getMaximumPoolSize()!==1||executor.getActiveCount()!==0||!executor.getQueue().isEmpty())throw Error('Existing native single-worker executor must be idle; no second executor is created');
 var taskSetter=Java.type('org.openpnp.spi.base.AbstractMachine').class.getDeclaredMethod('setTaskThread',Java.type('java.lang.Thread').class);taskSetter.setAccessible(true);
 function taskOwner(thread){taskSetter.invoke(m,Java.to([thread],'java.lang.Object[]'));}
 function settle(){var delay=Math.max(200,Number(top.getSettleTimeMs()),Number(bottom.getSettleTimeMs()));if(!isFinite(delay)||delay>3000)throw Error('Unreviewed camera settle interval');java.lang.Thread.sleep(Math.ceil(delay));}
 var initial=freeze(snapshot());PasteSurveyRequest.compareExact(initial.raw,q.expectedRaw,'expected raw');PasteSurveyRequest.compareExact(initial.driver,q.expectedDriver,'expected driver');comparePoses(initial.nativePoses,q.expectedNativePoses);
 var out=new F(root+'automation/evidence/paste-camera-led-'+q.id);if(!out.mkdir())throw Error('LED restore UUID already claimed; no retry');
 var r={schema:1,id:q.id,status:'claimed',startedAt:new Date().toISOString(),request:q,beforeQuerySnapshot:initial,transitions:[],motionSubmitted:false,positionQueryAckTimeoutMs:nativePositionAckTimeout,positionReportPollTimeoutMs:3000,nativeLEDLineTimeoutMs:nativeActuationTimeout,commands:[],actuationSubmitted:false,actuationPending:false,physicalAcceptanceEstablished:false,calibrationEstablished:false,noReplay:true};
 function save(status){r.status=status;r.transitions.push({status:status,time:new Date().toISOString()});Fs.write(new F(out,'report.json').toPath(),bytes(JSON.stringify(r,null,2)+'\n'));}
 save('preflight-before-any-controller-query');
 function query(saved,label){
  // Preserve pre-query numbers: native M114 parsing may update driver coordinates.
  stateGate();if(configHash()!==q.liveConfigurationSha256)throw Error('Configuration changed before position query');if(!executor.getQueue().isEmpty())throw Error('Competing native work before query');
  var current=snapshot();PasteSurveyRequest.compareExact(current.raw,saved.raw,'immutable query raw');PasteSurveyRequest.compareExact(current.driver,saved.driver,'immutable query driver');comparePoses(current.nativePoses,saved.nativePoses);
  r[label]={saved:saved,responses:[]};var entry=r[label];append(d.receiveResponses(),entry.responses);checkedLines(entry.responses);
  if(entry.responses.some(function(x){return positionPattern.matcher(x).matches();}))throw Error('Unclaimed stale position report');
  r.transportUncertain=true;r.controllerQuerySubmitted=true;save(label+'-query-started');
  var observed=d.getReportedLocation(3000),reported={};for each(var a in observed.getControllerAxes())reported[String(a.getLetter())]=Number(observed.getCoordinate(a));entry.reported=reported;
  collect(positionRegex,entry);var delimiter=-1;entry.responses.forEach(function(x,i){if(positionPattern.matcher(x).matches())delimiter=i;});if(delimiter<0)throw Error('Fresh position delimiter absent');
  if(!entry.responses.slice(delimiter+1).some(function(x){return /^ok/.test(x);}))collect('^ok.*',entry);
  append(d.receiveResponses(),entry.responses);checkedLines(entry.responses);
  PasteSurveyRequest.compareReported(reported,saved.raw,saved.driver);entry.afterQuerySnapshot=snapshot();PasteSurveyRequest.compareExact(entry.afterQuerySnapshot.raw,saved.raw,'query unchanged raw');comparePoses(entry.afterQuerySnapshot.nativePoses,saved.nativePoses);
  r.transportUncertain=false;save(label+'-reported-and-verified');
 }
 function capture(camera,name){
  if(String(camera.getClass().getName())!=='org.openpnp.machine.reference.camera.OpenPnpCaptureCamera')throw Error('Unknown camera capture implementation');
  var open=camera.getClass().getDeclaredMethod('isOpen');open.setAccessible(true);if(!open.invoke(camera))throw Error('Camera stream not already open; no reopen');
  var image=camera.captureRaw();if(image==null||!I.write(image,'png',new F(out,name+'.png')))throw Error('Raw capture failed');return {image:image,path:name+'.png',width:image.getWidth(),height:image.getHeight()};
 }
 function append(javaLines,target){for each(var line in javaLines)target.push(String(line.getLine()));}
 function checkedLines(lines){PasteConnectionPolicy.responses(lines);lines.forEach(function(line){if(/unknown command|halted|fatal|\bkilled\b/i.test(line))throw Error('Unexpected controller fault response: '+line);});}
 function collect(regex,record){var list=d.receiveResponses(regex,3000,new (Java.type('org.openpnp.machine.reference.driver.GcodeDriver$TimeoutAction'))({apply:function(lines){append(lines,record.responses);checkedLines(record.responses);save('response-timeout');throw new java.lang.Exception('LED response timeout; no retry');}}));append(list,record.responses);checkedLines(record.responses);}
 function restoreLED(){
  stateGate();if(configHash()!==q.liveConfigurationSha256)throw Error('Configuration changed before LED command');
  var stationary=snapshot();PasteSurveyRequest.compareExact(stationary.raw,initial.raw,'pre-LED raw');PasteSurveyRequest.compareExact(stationary.driver,r.before.afterQuerySnapshot.driver,'pre-LED driver');comparePoses(stationary.nativePoses,initial.nativePoses);
  var stale=[];append(d.receiveResponses(),stale);checkedLines(stale);if(stale.length)throw Error('Unsolicited response before LED restore');
  var entry={command:'M150 P255 R255 U255 B255',responses:[],acknowledged:false};r.commands.push(entry);
  r.transportUncertain=true;r.actuationSubmitted=true;r.actuationPending=true;save('fixed-native-LED-on-started');
  // Deliberately bypass ReferenceActuator and its null-head completion path.
  // Exact boolean template expands to this single LED line; no raw G-code dispatch.
  d.actuate(led,true);
  collect('^ok.*',entry);append(d.receiveResponses(),entry.responses);checkedLines(entry.responses);
  if(entry.responses.filter(function(x){return /^ok/.test(x);}).length!==1)throw Error('Expected exactly one LED line ACK');
  entry.acknowledged=true;r.transportUncertain=false;r.actuationPending=false;r.ledOnAcknowledged=true;r.actuationCacheNotUpdated=true;save('fixed-native-LED-on-acknowledged');
 }
 save('queued-on-existing-native-executor');
 try{executor.submit(new (Java.type('java.util.concurrent.Callable'))({call:function(){
 var ownedTask=false,keepBusy=false;
 try{
  if(m.isBusy()||!executor.getQueue().isEmpty())throw Error('Native task ownership changed before LED restore');
  taskOwner(java.lang.Thread.currentThread());ownedTask=true;m.fireMachineBusy(true);
  PasteCameraLED.validate(q,Number(java.lang.System.currentTimeMillis()),jvm);stateGate();
  if(configHash()!==q.liveConfigurationSha256)throw Error('Configuration changed before native task');
  var taskStart=snapshot();PasteSurveyRequest.compareExact(taskStart.raw,initial.raw,'queued raw');PasteSurveyRequest.compareExact(taskStart.driver,initial.driver,'queued driver');comparePoses(taskStart.nativePoses,initial.nativePoses);
  query(initial,'before');PasteSurveyRequest.compareExact(snapshot().raw,initial.raw,'post-query unchanged raw');
  settle();var beforeTop=capture(top,'top-before-raw'),beforeBottom=capture(bottom,'bottom-before-raw');r.beforeImages={top:{path:beforeTop.path,width:beforeTop.width,height:beforeTop.height},bottom:{path:beforeBottom.path,width:beforeBottom.width,height:beforeBottom.height}};save('before-images-captured');
  restoreLED();
  var after=snapshot();r.afterQuerySnapshot=after;PasteSurveyRequest.compareExact(after.raw,initial.raw,'stationary raw');comparePoses(after.nativePoses,initial.nativePoses);
  query(after,'after');r.afterQuerySnapshot=r.after.afterQuerySnapshot;PasteSurveyRequest.compareReported(r.after.reported,initial.raw,after.driver);PasteSurveyRequest.comparePostModel(r.after.reported,r.before.reported);
  r.controllerPositionVerified=true;save('stationary-controller-position-verified');settle();var afterTop=capture(top,'top-after-raw'),afterBottom=capture(bottom,'bottom-after-raw');r.afterImages={top:{path:afterTop.path,width:afterTop.width,height:afterTop.height},bottom:{path:afterBottom.path,width:afterBottom.width,height:afterBottom.height}};
  stateGate();if(configHash()!==q.liveConfigurationSha256)throw Error('Configuration changed during final images');
  r.uncertainCompletion=false;r.finishedAt=new Date().toISOString();save('completed-stationary-LED-restore-awaiting-review');
 }catch(e){
  r.error=String(e);r.uncertainCompletion=!!r.transportUncertain||r.actuationPending;r.ledMayBeOn=r.actuationSubmitted;r.auditIncomplete=true;r.finishedAt=new Date().toISOString();
  if(r.actuationSubmitted||r.controllerQuerySubmitted||r.transportUncertain){
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
