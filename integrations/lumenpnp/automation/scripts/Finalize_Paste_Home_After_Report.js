// One-shot completion of the exact G28/M400 success whose post-home audit rejected
// G28's normal position echo. NO home, movement, completion helper or replay.
// Only fresh M114 through the already connected native owner, then cache sync.
// Long unobserved idle may have released steppers: remain DISABLED and UNHOMED.
(function(){
 var C=Java.type('org.openpnp.model.Configuration'),F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8,
 MD=Java.type('java.security.MessageDigest'),MM=Java.type('org.openpnp.model.LengthUnit').Millimeters,AL=Java.type('org.openpnp.model.AxesLocation'),
 CT=Java.type('org.openpnp.machine.reference.driver.GcodeDriver$CommandType');
 var root='/home/lumen/lumenpnp/',m=C.get().getMachine(),planner=m.getMotionPlanner();
 function read(p){return String(new java.lang.String(Fs.readAllBytes(new F(p).toPath()),UTF));}
 function hash(bytes){var a=MD.getInstance('SHA-256').digest(bytes),s='';for(var i=0;i<a.length;i++)s+=('0'+((a[i]&255).toString(16))).slice(-2);return s;}
 function bytes(s){return new java.lang.String(s).getBytes(UTF);}
 function privateValue(className,name,obj){var f=Java.type(className).class.getDeclaredField(name);f.setAccessible(true);return f.get(obj);}
 function configHash(){var w=new java.io.StringWriter();C.createSerializer().write(m,w);return hash(bytes(String(w)));}

 var GD='org.openpnp.machine.reference.driver.GcodeDriver',AM='org.openpnp.spi.base.AbstractMachine',AP='org.openpnp.machine.reference.driver.AbstractMotionPlanner';
 function field(c,n){var f=Java.type(c).class.getDeclaredField(n);f.setAccessible(true);return f;}
 var failedPath=root+'automation/evidence/paste-reset-home-7516c2b5-1cf8-4a92-baa0-e09352377a80/report.json',failedHash='5eaec087f1c2e62382e9b38057ec8f8eaedfe6de7e391fdce2671eb9687474a5';
 var sourcePath=root+'automation/evidence/paste-model-state-1790791810364/report.json',sourceHash='99bd95c42b692e3d189682c7244b46246213a5ebeb08bcfb6025dcb271a229ac';
 var configSha='858c9955396bfd84c7688e70c689826bb6a0c0eb8c3a43b791e89323bdd705ca';
 function hashedJson(path,expected){var b=Fs.readAllBytes(new F(path).toPath());if(hash(b)!==expected)throw Error('Reviewed evidence changed: '+path);return JSON.parse(String(new java.lang.String(b,UTF)));}
 var failed=hashedJson(failedPath,failedHash),source=hashedJson(sourcePath,sourceHash);
 var jvm=Number(Java.type('java.lang.management.ManagementFactory').getRuntimeMXBean().getStartTime());
 if(jvm!==1790731396900||jvm!==failed.request.jvmStartMs||jvm!==source.jvmStartMs)throw Error('Exact native JVM session required');
 if(!Java.type('javax.swing.SwingUtilities').isEventDispatchThread())throw Error('Reviewed synchronous dispatcher required');
 if(failed.status!=='failed-no-retry-no-recovery-motion'||failed.error!=='Error: Stale position response before fresh query'||failed.motionSubmitted!==true||failed.nativeMotionCompletionReported!==true||failed.executorQuarantined!==true||failed.queuedTasksCancelled!==0||failed.after.reported!==undefined||failed.liveConfigurationSha256!==configSha||failed.request.enableAfterVerifiedHome!==true)throw Error('Not the exact completed-home audit failure');
 if(source.scope!=='pure-model-state-no-controller-access'||source.liveConfigurationSha256!==configSha||source.enabled!==false||source.homed!==false||source.busy!==true||source.executor.shutdown!==true||source.executor.terminated!==true||source.executor.active!==0||source.executor.queued!==0||source.taskOwner.alive!==false||source.drivers.length!==1||source.drivers[0].readerAlive!==true||source.drivers[0].error!==null)throw Error('Unexpected diagnostic source');
 var sourceMs=Date.parse(source.time),now=Number(java.lang.System.currentTimeMillis());if(!isFinite(sourceMs)||sourceMs>now||now-sourceMs>1800000)throw Error('Fresh model diagnostic required (30 minutes)');
 eval(read(root+'automation/paste/z-observation.cjs'));eval(read(root+'automation/paste/reset-home.cjs'));eval(read(root+'automation/paste/native-air.cjs'));eval(read(root+'automation/paste/connection-policy.cjs'));
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
 function snapshot(){var s={raw:{},driver:{},nativePoses:poses()};Object.keys(axes).forEach(function(k){s.raw[k]=Number(axes[k].getCoordinate());s.driver[k]=Number(axes[k].getDriverCoordinate());});return s;}
 var originalReader=privateValue('org.openpnp.machine.reference.driver.GcodeDriver','readerThread',d),originalCommands=d.commands;
 function stateGate(){
  function inert(a){if(String(a.getClass().getName())!=='org.openpnp.machine.reference.ReferenceActuator'||String(a.getHomedActuation())!=='LeaveAsIs'||['LeaveAsIs','AssumeUnknown'].indexOf(String(a.getEnabledActuation()))<0||String(a.getDisabledActuation())!=='LeaveAsIs')throw Error('Machine-state callback may actuate');}for each(var a in m.getActuators())inert(a);for each(var h in m.getHeads()){if(h.getPumpActuator()!=null)throw Error('Configured head pump callback');for each(var a in h.getActuators())inert(a);}
  if(d.commands!==originalCommands||originalReader==null||!originalReader.isAlive()||privateValue('org.openpnp.machine.reference.driver.GcodeDriver','readerThread',d)!==originalReader||privateValue('org.openpnp.machine.reference.driver.GcodeDriver','errorResponse',d)!=null)throw Error('Reader/commands changed or prior native error');
  if(!m.isBusy()||m.isEnabled()||m.isHomed()||String(state.get(panel))!=='Stopped')throw Error('Recovery requires idle UI-disabled unhomed machine and stopped job');
  if(!d.isSyncInitialLocation()||planner.isHomed())throw Error('Expected unhomed state');
  if(JSON.stringify(PasteConnectionPolicy.tokens(d.getCommand(null,CT.HOME_COMMAND)))!==JSON.stringify(['{Acceleration:M204 S%.2f','G28']))throw Error('Native HOME template changed');
  var homeRegex=d.getCommand(null,CT.HOME_COMPLETE_REGEX);if(homeRegex!=null&&String(homeRegex).trim())throw Error('Hidden home response consumer');
  if(d.getCommand(null,CT.ENABLE_COMMAND)!=null&&String(d.getCommand(null,CT.ENABLE_COMMAND)).trim())throw Error('Enable command must be absent');
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

 var exField=field(AM,'executor'),ownerField=field(AM,'taskThread'),oldExecutor=exField.get(m),oldOwner=ownerField.get(m),fresh=null;
 var disk=new F(C.get().getConfigurationDirectory(),'machine.xml'),backup=new F(failed.backup),backupDisk=new F(backup,'disk-machine-before.xml'),backupLive=new F(backup,'live-machine-before.xml');
 if(String(backup)!==root+'.local-machine-backups/paste-reset-home-'+failed.id||!backupDisk.isFile()||!backupLive.isFile())throw Error('Exact pre-home backup missing');
 var diskHash='cdc90eff785f99b030a662ff3375b3f2e47dd1fbf624f382edccd367278cc4d8';
 function configGate(){if(configHash()!==configSha||hash(Fs.readAllBytes(backupLive.toPath()))!==configSha||hash(Fs.readAllBytes(disk.toPath()))!==diskHash||hash(Fs.readAllBytes(backupDisk.toPath()))!==diskHash)throw Error('Current or pre-home backup configuration changed');}
 function expectedCaches(){var s=snapshot();PasteZObservation.compareExact(s.raw,failed.after.saved.raw,'failed-home raw');PasteZObservation.compareExact(s.driver,failed.after.saved.driver,'failed-home driver');comparePoses(s.nativePoses,failed.after.saved.nativePoses);source.axes.forEach(function(a){if(!axes[a.letter]||String(axes[a.letter].getId())!==a.id)throw Error('Diagnostic axis changed');PasteZObservation.close(s.raw[a.letter],a.model,0.0001,'diagnostic model');PasteZObservation.close(s.driver[a.letter],a.driver,0.0001,'diagnostic driver');});return s;}
 function oldExecutorGate(){if(oldExecutor==null||!oldExecutor.isShutdown()||!oldExecutor.isTerminated()||oldExecutor.getActiveCount()!==0||!oldExecutor.getQueue().isEmpty()||oldOwner==null||oldOwner.isAlive()||String(oldOwner.getName())!==source.taskOwner.name)throw Error('Exact dead empty executor required');}
 function initialGate(){stateGate();configGate();expectedCaches();oldExecutorGate();if(exField.get(m)!==oldExecutor||ownerField.get(m)!==oldOwner)throw Error('Quarantined executor owner changed');}
 initialGate();
 var out=new F(root+'automation/evidence/paste-home-finalize-'+failed.id);if(!out.mkdir())throw Error('Finalizer already claimed; no retry');
 var r={schema:1,scope:'exact-home-audit-finalization-no-motion',failedPath:failedPath,failedSha256:failedHash,sourcePath:sourcePath,sourceSha256:sourceHash,jvmStartMs:jvm,startedAt:new Date().toISOString(),liveConfigurationSha256:configSha,beforeQuerySnapshot:snapshot(),priorCompletedHomeResponses:failed.after.responses,noHome:true,noMotion:true,noEnable:true,noReplay:true,absolutePhysicalPositionUnknown:true,configurationSaved:false,physicalAcceptanceEstablished:false,calibrationEstablished:false,positionQueryAckTimeoutMs:nativePositionAckTimeout,transitions:[]};
 function save(status){r.status=status;r.transitions.push({status:status,time:new Date().toISOString()});Fs.write(new F(out,'report.json').toPath(),bytes(JSON.stringify(r,null,2)+'\n'));}
 function append(lines,target){for each(var line in lines)target.push(String(line.getLine()));}
 function checkedLines(lines){PasteConnectionPolicy.responses(lines);lines.forEach(function(line){if(/unknown command|halted|fatal|\bkilled\b/i.test(line))throw Error('Controller fault: '+line);});}
 var positionRegex='^.*X:(?<X>-?\\d+\\.\\d+)\\s*Y:(?<Y>-?\\d+\\.\\d+)\\s*Z:(?<Z>-?\\d+\\.\\d+)\\s*A:(?<A>-?\\d+\\.\\d+)\\s*B:(?<B>-?\\d+\\.\\d+).*';
 if(String(d.getCommand(null,CT.POSITION_REPORT_REGEX))!==positionRegex)throw Error('Audited position-report delimiter changed');
 var positionPattern=java.util.regex.Pattern.compile(positionRegex);

 function collect(regex,entry){var list=d.receiveResponses(regex,3000,new (Java.type('org.openpnp.machine.reference.driver.GcodeDriver$TimeoutAction'))({apply:function(lines){append(lines,entry.responses);checkedLines(entry.responses);save('response-timeout');throw new java.lang.Exception('Position response timeout; no retry');}}));append(list,entry.responses);checkedLines(entry.responses);}
 function workGate(){stateGate();configGate();oldExecutorGate();if(exField.get(m)!==fresh||ownerField.get(m)!==java.lang.Thread.currentThread()||fresh.isShutdown()||fresh.getActiveCount()!==1||!fresh.getQueue().isEmpty())throw Error('Finalizer worker ownership changed');}
 checkedLines(failed.after.responses);PasteResetHome.priorHomeResponses(failed.after.responses,failed.before.reported,PasteZObservation);
 save('exact-failure-and-backup-verified');
 initialGate();
 fresh=new (Java.type('java.util.concurrent.ThreadPoolExecutor'))(1,1,1,Java.type('java.util.concurrent.TimeUnit').SECONDS,new (Java.type('java.util.concurrent.LinkedBlockingQueue'))());
 if(fresh.getPoolSize()!==0||fresh.getActiveCount()!==0||!fresh.getQueue().isEmpty())throw Error('Replacement executor unexpectedly active');
 // Busy remains true throughout. Only the proven terminated empty executor is replaced.
 exField.set(m,fresh);
 try{fresh.submit(new (Java.type('java.util.concurrent.Callable'))({call:function(){
  var complete=false;
  try{
   if(exField.get(m)!==fresh||ownerField.get(m)!==oldOwner||!m.isBusy()||!fresh.getQueue().isEmpty())throw Error('Native task ownership changed');
   ownerField.set(m,java.lang.Thread.currentThread());workGate();expectedCaches();
   var entry={priorResponses:[],responses:[]};r.freshPosition=entry;
   append(d.receiveResponses(),entry.priorResponses);checkedLines(entry.priorResponses);
   // The failed script already drained G28/M400. Any new position before M114
   // indicates intervening controller work and is never accepted as fresh evidence.
   if(entry.priorResponses.some(function(line){return positionPattern.matcher(line).matches();}))throw Error('Unexpected position before finalizer M114');
   r.controllerQuerySubmitted=true;r.transportUncertain=true;save('fresh-M114-submitted');
   var observed=d.getReportedLocation(3000),reported={};for each(var a in observed.getControllerAxes())reported[String(a.getLetter())]=Number(observed.getCoordinate(a));
   collect(positionRegex,entry);
   var delimiter=-1;entry.responses.forEach(function(line,i){if(positionPattern.matcher(line).matches())delimiter=i;});
   if(delimiter<0)throw Error('Fresh M114 delimiter missing');
   if(!entry.responses.slice(delimiter+1).some(function(line){return /^ok/.test(line);}))collect('^ok.*',entry);
   append(d.receiveResponses(),entry.responses);checkedLines(entry.responses);
   PasteResetHome.freshHomeResponses(entry.responses,reported,failed.before.reported,PasteZObservation);
   entry.reported=reported;r.transportUncertain=false;r.controllerPositionVerified=true;save('fresh-M114-full-report-and-following-ACK-verified');
   workGate();var queried=snapshot();PasteZObservation.compareExact(queried.raw,failed.after.saved.raw,'query unchanged raw');comparePoses(queried.nativePoses,failed.after.saved.nativePoses);PasteZObservation.compareExact(queried.driver,reported,'native report updated driver');
   var location=new AL();Object.keys(axes).forEach(function(k){location=location.put(new AL(axes[k],reported[k]));});location.setToDriverCoordinates(d);location.setToCoordinates();
   var synced=snapshot();PasteZObservation.compareExact(synced.raw,reported,'synchronized model');PasteZObservation.compareExact(synced.driver,reported,'synchronized driver');r.afterQuerySnapshot=synced;
   workGate();
   // M114 proves the firmware coordinate cache, not physical registration after
   // prolonged idle. No mark-homed or enable operation is permitted here.
   configGate();stateGate();
   if(m.isEnabled()||m.isHomed()||planner.isHomed()||d.isMotionPending()||privateValue(AP,'motionCommands',planner).size()!==0||exField.get(m)!==fresh||ownerField.get(m)!==java.lang.Thread.currentThread()||!fresh.getQueue().isEmpty())throw Error('Final native state differs');
   var finalPose=snapshot();PasteZObservation.compareExact(finalPose.raw,reported,'final model');PasteZObservation.compareExact(finalPose.driver,reported,'final driver');comparePoses(finalPose.nativePoses,synced.nativePoses);
   r.diskUnchanged=true;r.machineEnabled=false;r.machineHomed=false;r.machineRemainsDisabledUnhomed=true;r.absolutePhysicalPositionUnknown=true;r.physicalRegistrationInvalidated=true;r.rotationUnchangedVerified=true;r.uncertainCompletion=false;r.finishedAt=new Date().toISOString();
   save('completed-home-cache-finalization-disabled-unhomed');complete=true;
  }catch(e){
   r.error=String(e);r.uncertainCompletion=true;r.auditIncomplete=true;r.finishedAt=new Date().toISOString();
   // Keep busy/owner quarantine; do not flush planner, disable, reconnect or retry.
   var pending;r.queuedTasksCancelled=0;while((pending=fresh.getQueue().poll())!=null){if(pending instanceof Java.type('java.util.concurrent.Future'))pending.cancel(false);r.queuedTasksCancelled++;}fresh.shutdown();r.executorQuarantined=true;save('failed-no-retry-no-recovery-motion');
  }finally{
   if(complete){ownerField.set(m,null);m.fireMachineBusy(false);}
   print(String(out));
  }
  return null;
 }}));}catch(e){fresh.shutdown();r.error=String(e);save('enqueue-failed-retaining-busy-no-motion');throw e;}
})();
