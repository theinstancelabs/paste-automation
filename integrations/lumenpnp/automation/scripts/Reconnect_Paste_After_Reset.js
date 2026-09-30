// STAGED post-reset native reconnect and reported-frame model sync. Parent dispatch only.
// No enable, home, movement, saved configuration writes or separate serial owner.
// Native connect DOES send G21/G90 and the audited VAC-sensor M260 setup.
// Synchronous on existing dispatcher: machine task queues can flush planner work.
(function(){
 var C=Java.type('org.openpnp.model.Configuration'),F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),
 UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8,Opt=Java.type('java.nio.file.StandardOpenOption'),
 GD=Java.type('org.openpnp.machine.reference.driver.GcodeDriver'),CT=Java.type('org.openpnp.machine.reference.driver.GcodeDriver$CommandType'),
 Digest=Java.type('java.security.MessageDigest');
 var root='/home/lumen/lumenpnp/', port='/dev/serial/by-id/usb-STMicroelectronics_MARLIN_OPULO_LUMEN_REV5_CDC_in_FS_Mode_387932683335-if00';
 function read(file){return String(new java.lang.String(Fs.readAllBytes(new F(file).toPath()),UTF));}
 function hashBytes(bytes){var value=Digest.getInstance('SHA-256').digest(bytes),out='';for(var i=0;i<value.length;i++)out+=('0'+((value[i]&255).toString(16))).slice(-2);return out;}
 function hash(file){return hashBytes(Fs.readAllBytes(file.toPath()));}
 function write(file,text,fresh){Fs.write(file.toPath(),new java.lang.String(text).getBytes(UTF),fresh?Java.to([Opt.CREATE_NEW,Opt.WRITE],'java.nio.file.OpenOption[]'):Java.to([Opt.CREATE,Opt.TRUNCATE_EXISTING,Opt.WRITE],'java.nio.file.OpenOption[]'));}
 function privateValue(type,name,obj){var field=type.class.getDeclaredField(name);field.setAccessible(true);return field.get(obj);}
 eval(read(root+'automation/paste/connection-policy.cjs'));
 var requestBytes=Fs.readAllBytes(new F(root+'automation/plans/paste-reset-connect-request.json').toPath()),request=JSON.parse(String(new java.lang.String(requestBytes,UTF))),jvm=Number(Java.type('java.lang.management.ManagementFactory').getRuntimeMXBean().getStartTime()),now=Number(java.lang.System.currentTimeMillis());
 if(request.schema!==1||request.scope!=='post-reset-connect-and-sync-unhomed'||typeof request.createdMs!=='number'||!isFinite(request.createdMs)||request.createdMs>now||now-request.createdMs>300000||request.jvmStartMs!==jvm||request.reviewedNativeConnectAndUnhomedSync!==true||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(request.id)||typeof request.operator!=='string'||!request.operator.trim()||!request.invalidationEvidence||!/^[a-f0-9]{64}$/.test(request.invalidationEvidence.sha256)||typeof request.invalidationEvidence.path!=='string'||request.invalidationEvidence.path.charAt(0)!=='/')throw Error('Fresh reviewed reset-connect request required');
 var invalidationBytes=Fs.readAllBytes(new F(request.invalidationEvidence.path).toPath());if(hashBytes(invalidationBytes)!==request.invalidationEvidence.sha256)throw Error('Invalidation record changed');var invalidation=JSON.parse(String(new java.lang.String(invalidationBytes,UTF)));
 if(invalidation.status!=='reset-invalidated-disabled-unhomed-disconnected-awaiting-separate-connect'||invalidation.jvmStartMs!==jvm||invalidation.noControllerCommands!==true||invalidation.noMotion!==true||invalidation.diskUnchanged!==true||invalidation.cachedCoordinatesRemainUntrusted!==true)throw Error('Successful exact native reset invalidation required');
 eval(read(root+'automation/paste/native-air.cjs'));
 var cfg=C.get(),m=cfg.getMachine(),panel=Java.type('org.openpnp.gui.MainFrame').get().getJobTab(),stateField=panel.getClass().getDeclaredField('state');stateField.setAccessible(true);
 if(m.getDrivers().size()!==1)throw Error('Exactly one audited native driver required');
 var d=m.getDrivers().get(0);
 if(String(d.getClass().getName())!=='org.openpnp.machine.reference.driver.GcodeDriver')throw Error('Unknown driver class');
 var serial=d.getSerial(), SP=Java.type('org.openpnp.machine.reference.driver.SerialPortCommunications');
 var jar=new F(GD.class.getProtectionDomain().getCodeSource().getLocation().toURI());
 if(hash(jar)!=='bcd34923ae91d61a96b98b4c82c93cdc90093ff94292270fd0a18fc6f96f7752')throw Error('Installed driver jar differs from inspected bytecode');
 function auditState(){
  var reader=privateValue(GD,'readerThread',d),nativePort=privateValue(SP,'serialPort',serial),head=m.getDefaultHead(),n2=head.getNozzleByName('N2'),held=false;
  for each(var h in m.getHeads())for each(var n in h.getNozzles())if(n.getPart()!=null||n.getPartsFeeder()!=null)held=true;
  var quarantined=n2!=null&&String(n2.getId())==='NOZ1710829fd33a0170'&&n2.getNozzleTip()==null&&n2.getCompatibleNozzleTips().size()===0&&n2.getRotationModeOffset()==null&&!n2.isChangerEnabled()&&!n2.getManualNozzleTipChangeLocation().isInitialized()&&!m.getPnpJobProcessor().isPreRotateAllNozzles();
  var value={enabled:m.isEnabled(),homed:m.isHomed(),busy:m.isBusy(),jobState:String(stateField.get(panel)),driverCount:Number(m.getDrivers().size()),driverClass:String(d.getClass().getName()),driverId:String(d.getId()),connected:(String(privateValue(GD,'connected',d))==='true'),readerAlive:reader!=null&&reader.isAlive(),serialOpen:nativePort!=null&&nativePort.isOpen(),serialClass:String(serial.getClass().getName()),communicationsType:String(d.getCommunicationsType()),simulation:d.isInSimulationMode(),baud:Number(serial.getBaud()),flowControl:String(serial.getFlowControl()),dataBits:String(serial.getDataBits()),stopBits:String(serial.getStopBits()),parity:String(serial.getParity()),dtr:serial.isSetDtr(),rts:serial.isSetRts(),lineEnding:String(d.getLineEndingType()),quarantined:quarantined,heldPart:held};
  PasteConnectionPolicy.checkState(value);return value;
 }
 var startState=auditState(),oldPort=String(serial.getPortName());
 for each(var axis in new (Java.type('org.openpnp.model.AxesLocation'))(m).drivenBy(d).getControllerAxes()){var prior=invalidation.afterCachedAxes[String(axis.getLetter())];if(!prior||prior.id!==String(axis.getId())||Math.abs(Number(axis.getCoordinate())-prior.model)>.0001||Math.abs(Number(axis.getDriverCoordinate())-prior.driver)>.0001)throw Error('Untrusted cached state changed since invalidation');}
 if(Number(d.getConnectWaitTimeMilliseconds())!==6000||Number(d.getTimeoutMilliseconds())!==10000)throw Error('Driver timing differs from inspected configuration');
 var connect=String(d.getCommand(null,CT.CONNECT_COMMAND)),enable=d.getCommand(null,CT.ENABLE_COMMAND),disable=d.getCommand(null,CT.DISABLE_COMMAND);
 PasteConnectionPolicy.checkCommands(connect,enable,disable);
 // Reject unexpected stale port rather than reassign an unrelated driver.
 if(oldPort!==port)throw Error('Unexpected prior configured port '+oldPort);
 var portFile=new F(port);
 function device(){
  if(!Fs.isSymbolicLink(portFile.toPath())||!portFile.exists())throw Error('Expected exact STMicroelectronics Marlin by-id device missing');
  var resolved=String(portFile.getCanonicalPath());if(!/^\/dev\/ttyACM\d+$/.test(resolved))throw Error('Unexpected by-id target '+resolved);
  return resolved;
 }
 var resolved=device();if(resolved!=='/dev/ttyACM2')throw Error('Reviewed reset device enumeration changed');
 function noOwner(){
  if(device()!==resolved)throw Error('Controller enumeration changed during review');
  var pb=new java.lang.ProcessBuilder(Java.to(['/usr/bin/fuser','-v',resolved],'java.lang.String[]'));pb.redirectErrorStream(true);
  var process=pb.start();if(!process.waitFor(3,Java.type('java.util.concurrent.TimeUnit').SECONDS)){process.destroyForcibly();throw Error('Serial ownership check timed out');}
  var output=String(new java.lang.String(process.getInputStream().readAllBytes(),UTF));
  PasteConnectionPolicy.noOwner(Number(process.exitValue()),output);
 }
 // In particular, a browser Web Serial owner causes this to fail BEFORE any
 // configuration mutation or driver connection. Do not terminate its owner.
 noOwner();
 var stamp=request.id,backup=new F(root+'.local-machine-backups/paste-reset-connect-'+stamp),evidence=new F(root+'automation/evidence/paste-reset-connect-'+stamp);
 if(!backup.mkdirs()||!evidence.mkdirs())throw Error('Cannot claim fresh backup/evidence directories');
 var disk=new F(cfg.getConfigurationDirectory(),'machine.xml'),copy=new F(backup,'disk-machine-before.xml');
 if(!disk.isFile())throw Error('Saved machine.xml missing');
 var diskHash=hash(disk);Fs.copy(disk.toPath(),copy.toPath());if(hash(copy)!==diskHash||hash(disk)!==diskHash)throw Error('Disk backup hash mismatch');
 var live=new java.io.StringWriter();C.createSerializer().write(m,live);if(hashBytes(new java.lang.String(String(live)).getBytes(UTF))!==invalidation.liveConfigurationSha256)throw Error('Invalidated configuration changed');var liveFile=new F(backup,'live-machine-before.xml');write(liveFile,String(live),true);
 if(hash(liveFile)!==hashBytes(new java.lang.String(String(live)).getBytes(UTF)))throw Error('Live backup hash mismatch');
 var report={request:request,jvmStartMs:jvm,scope:'post-reset-native-connect-and-reported-frame-sync',homingRequired:true,controllerPoseTrusted:false,time:new Date().toISOString(),status:'preflight',machineState:startState,deviceById:port,resolvedDevice:resolved,previousPort:oldPort,driverId:String(d.getId()),driverJarSha256:hash(jar),connectCommands:PasteConnectionPolicy.tokens(connect),connectSideEffects:'G21 millimeters, G90 absolute mode, M260 VAC sensor initialization; no movement/enable/home commands. USB connection may reset controller; homing remains invalid.',backup:String(backup),diskMachineSha256:diskHash,liveBackupSha256:hash(liveFile),queries:[],noAutomaticRetry:true,physicalVerification:false,persistence:'No cfg.save; normal app exit can persist in-memory port change. Reinspect after restart.'};
 function save(){write(new F(evidence,'report.json'),JSON.stringify(report,null,2)+'\n',false);}
 save();
 var connectionAttempted=false;
 try{
  auditState();noOwner();
  // Audited model setter only. Preserve all other serial and machine settings.
  if(String(serial.getPortName())!==port)throw Error('Port identity changed');
  report.status='existing-port-verified-no-setting-change';save();
  auditState();noOwner();PasteConnectionPolicy.checkCommands(d.getCommand(null,CT.CONNECT_COMMAND),d.getCommand(null,CT.ENABLE_COMMAND),d.getCommand(null,CT.DISABLE_COMMAND));
  if(String(d.getCommand(null,CT.COMMAND_ERROR_REGEX))!==NativePasteAir.nativeErrorRegex||privateValue(GD,'errorResponse',d)!=null)throw Error('Native error latch absent or prior error');
  connectionAttempted=true;report.status='connecting-native-owner';save();d.connect();
  if(!(String(privateValue(GD,'connected',d))==='true')||m.isEnabled()||m.isHomed())throw Error('Unexpected state after native connect');
  report.status='connected-disabled-unhomed';report.connectResponses=[];
  for each(var line in d.receiveResponses())report.connectResponses.push(String(line.getLine()));save();PasteConnectionPolicy.responses(report.connectResponses);
  function append(list,to){for each(var line in list)to.push(String(line.getLine()));}
  function collect(regex,to){var list=d.receiveResponses(regex,3000,new (Java.type('org.openpnp.machine.reference.driver.GcodeDriver$TimeoutAction'))({apply:function(lines){append(lines,to);PasteConnectionPolicy.responses(to);throw new java.lang.Exception('Reset inspection response timeout; no retry');}}));append(list,to);PasteConnectionPolicy.responses(to);}
  // Await the final CONNECT ACK in the full queue if its publication lagged confirmation.
  if(report.connectResponses.filter(function(x){return /^ok/.test(x);}).length<PasteConnectionPolicy.tokens(connect).length)collect('^ok.*',report.connectResponses);
  if(report.connectResponses.filter(function(x){return /^ok/.test(x);}).length!==PasteConnectionPolicy.tokens(connect).length)throw Error('Connect full-queue ACK count differs from audited lines');
  for each(var command in ['M115','M503']){
   if(m.isEnabled()||m.isHomed())throw Error('Machine state changed during inspection');
   var q={command:command,status:'sent',responses:[]};report.queries.push(q);save();
   d.sendCommand(command,3000);
   collect('^ok.*',q.responses);append(d.receiveResponses(),q.responses);
   PasteConnectionPolicy.responses(q.responses);q.status='acknowledged';save();
  }
  var identity=report.queries[0].responses.join('\n'),settings=report.queries[1].responses.join('\n');
  if(!/FIRMWARE_NAME:.*Marlin/.test(identity)||!/MACHINE_TYPE:LumenPnP/.test(identity)||!/AXIS_COUNT:5/.test(identity))throw Error('Unrecognized/absent live firmware identity; inspect captured responses');
  if(!/M92\s/.test(settings))throw Error('M503 did not capture expected settings payload; ACK alone is insufficient');
  report.status='queried-native-owner';save();
  var AL=Java.type('org.openpnp.model.AxesLocation'),planner=m.getMotionPlanner(),position='^.*X:(?<X>-?\\d+\\.\\d+)\\s*Y:(?<Y>-?\\d+\\.\\d+)\\s*Z:(?<Z>-?\\d+\\.\\d+)\\s*A:(?<A>-?\\d+\\.\\d+)\\s*B:(?<B>-?\\d+\\.\\d+).*',pattern=java.util.regex.Pattern.compile(position);
  function idle(){if(m.isEnabled()||m.isHomed()||m.isBusy()||d.isMotionPending()||String(privateValue(GD,'connected',d))!=='true'||privateValue(GD,'readerThread',d)==null||!privateValue(GD,'readerThread',d).isAlive()||privateValue(GD,'errorResponse',d)!=null)throw Error('Connected disabled/unhomed idle state changed');var cls=Java.type('org.openpnp.machine.reference.driver.AbstractMotionPlanner');if(privateValue(cls,'motionCommands',planner).size()!==0)throw Error('Motion queue nonempty');var sub=privateValue(cls,'subordinateMotion',planner),sq=privateValue(Java.type('org.openpnp.machine.reference.driver.AbstractMotionPlanner$SubordinateMotion'),'queue',sub);if(sq!=null&&!sq.isEmpty())throw Error('Subordinate axes queued');}
  function axes(){var r={};for each(var a in new AL(m).drivenBy(d).getControllerAxes())r[String(a.getLetter())]={model:Number(a.getCoordinate()),driver:Number(a.getDriverCoordinate())};return r;}
  idle();if(String(d.getCommand(null,CT.POSITION_REPORT_REGEX))!==position||['M114','M114 ; get position'].indexOf(String(d.getCommand(null,CT.GET_POSITION_COMMAND)).trim())<0)throw Error('Native position templates changed');
  report.cachedBeforeQueryUntrusted=axes();report.positionResponses=[];append(d.receiveResponses(),report.positionResponses);PasteConnectionPolicy.responses(report.positionResponses);if(report.positionResponses.length)throw Error('Unclaimed responses before reset-position query');
  report.status='reading-reset-controller-frame';save();var observed=d.getReportedLocation(3000);collect(position,report.positionResponses);var delimiter=-1;report.positionResponses.forEach(function(x,i){if(pattern.matcher(x).matches())delimiter=i;});if(delimiter<0)throw Error('Fresh position delimiter missing');if(!report.positionResponses.slice(delimiter+1).some(function(x){return /^ok/.test(x);}))collect('^ok.*',report.positionResponses);append(d.receiveResponses(),report.positionResponses);PasteConnectionPolicy.responses(report.positionResponses);
  report.reportedResetFrame={};for each(var a in observed.getControllerAxes()){var n=Number(observed.getCoordinate(a));if(!isFinite(n)||a.getDriver()!==d)throw Error('Invalid reported axis');report.reportedResetFrame[String(a.getLetter())]=n;}if(Object.keys(report.reportedResetFrame).sort().join(',')!=='A,B,X,Y,Z')throw Error('Incomplete reset frame');
  idle();observed.setToDriverCoordinates(d);observed.setToCoordinates();report.synchronizedModel=axes();Object.keys(report.reportedResetFrame).forEach(function(k){if(Math.abs(report.synchronizedModel[k].model-report.reportedResetFrame[k])>0.0001||Math.abs(report.synchronizedModel[k].driver-report.reportedResetFrame[k])>0.0001)throw Error('Reported reset-frame model sync failed');});idle();
  var finalLive=new java.io.StringWriter();C.createSerializer().write(m,finalLive);report.liveConfigurationAfterSha256=hashBytes(new java.lang.String(String(finalLive)).getBytes(UTF));if(report.liveConfigurationAfterSha256!==invalidation.liveConfigurationSha256)throw Error('Configuration changed during reconnect/sync');
  report.synchronizedSnapshot={raw:{},driver:{},nativePoses:{}};Object.keys(report.synchronizedModel).forEach(function(k){report.synchronizedSnapshot.raw[k]=report.synchronizedModel[k].model;report.synchronizedSnapshot.driver[k]=report.synchronizedModel[k].driver;});
  var head=m.getDefaultHead(),items={N1:head.getNozzleByName('N1'),N2:head.getNozzleByName('N2'),top:head.getDefaultCamera()},bottom=null;for each(var camera in m.getCameras())if(String(camera.getLooking())==='Up'){if(bottom!=null)throw Error('Ambiguous bottom camera');bottom=camera;}if(bottom==null)throw Error('Bottom camera missing');items.bottom=bottom;Object.keys(items).forEach(function(k){var p=items[k].getLocation().convertToUnits(Java.type('org.openpnp.model.LengthUnit').Millimeters);report.synchronizedSnapshot.nativePoses[k]={x:Number(p.getX()),y:Number(p.getY()),z:Number(p.getZ()),rotation:Number(p.getRotation())};});
  report.controllerFrameSynchronized=true;report.absolutePhysicalPositionKnown=false;report.controllerPoseTrusted=false;report.homingRequired=true;report.status='connected-disabled-unhomed-reported-frame-synchronized';
 }catch(e){report.status='failed-no-retry';report.error=String(e);throw e;}
 finally{
  if(connectionAttempted&&report.status!=='connected-disabled-unhomed-reported-frame-synchronized'){try{
   // Native disconnect can swallow close errors and clear references. Keep the
   // actual objects to verify closure, rather than trusting connected=false.
   var ownedNativePort=privateValue(SP,'serialPort',serial),ownedReader=privateValue(GD,'readerThread',d);
   d.disconnect();
   var afterNativePort=privateValue(SP,'serialPort',serial),afterReader=privateValue(GD,'readerThread',d);
   report.nativePortStillOpen=(ownedNativePort!=null&&ownedNativePort.isOpen())||(afterNativePort!=null&&afterNativePort.isOpen());
   report.readerStillAlive=(ownedReader!=null&&ownedReader.isAlive())||(afterReader!=null&&afterReader.isAlive());
   report.disconnected=!(String(privateValue(GD,'connected',d))==='true')&&!report.nativePortStillOpen&&!report.readerStillAlive;
  }catch(disconnectError){report.disconnectError=String(disconnectError);report.status='disconnect-failed';}}
  report.machineEnabledAfter=m.isEnabled();report.machineHomedAfter=m.isHomed();report.diskUnchanged=hash(disk)===diskHash;report.finished=new Date().toISOString();
  save();print(String(evidence));
  if(report.machineEnabledAfter||report.machineHomedAfter||!report.diskUnchanged||report.disconnectError||report.disconnected===false)throw Error('Unexpected final state; inspect '+evidence+'; no retry or motion');
 }
})();
