// Reviewed native-owner diagnostic. STAGED: parent dispatches after owner review.
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
 if(Number(d.getConnectWaitTimeMilliseconds())!==6000||Number(d.getTimeoutMilliseconds())!==10000)throw Error('Driver timing differs from inspected configuration');
 var connect=String(d.getCommand(null,CT.CONNECT_COMMAND)),enable=d.getCommand(null,CT.ENABLE_COMMAND),disable=d.getCommand(null,CT.DISABLE_COMMAND);
 PasteConnectionPolicy.checkCommands(connect,enable,disable);
 // Reject unexpected stale port rather than reassign an unrelated driver.
 if(['ttyACM0','/dev/ttyACM0',port].indexOf(oldPort)<0)throw Error('Unexpected prior configured port '+oldPort);
 var portFile=new F(port);
 function device(){
  if(!Fs.isSymbolicLink(portFile.toPath())||!portFile.exists())throw Error('Expected exact STMicroelectronics Marlin by-id device missing');
  var resolved=String(portFile.getCanonicalPath());if(!/^\/dev\/ttyACM\d+$/.test(resolved))throw Error('Unexpected by-id target '+resolved);
  return resolved;
 }
 var resolved=device();
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
 var stamp=String(java.lang.System.currentTimeMillis()),backup=new F(root+'.local-machine-backups/paste-connect-'+stamp),evidence=new F(root+'automation/evidence/paste-connect-'+stamp);
 if(!backup.mkdirs()||!evidence.mkdirs())throw Error('Cannot claim fresh backup/evidence directories');
 var disk=new F(cfg.getConfigurationDirectory(),'machine.xml'),copy=new F(backup,'disk-machine-before.xml');
 if(!disk.isFile())throw Error('Saved machine.xml missing');
 var diskHash=hash(disk);Fs.copy(disk.toPath(),copy.toPath());if(hash(copy)!==diskHash||hash(disk)!==diskHash)throw Error('Disk backup hash mismatch');
 var live=new java.io.StringWriter();C.createSerializer().write(m,live);var liveFile=new F(backup,'live-machine-before.xml');write(liveFile,String(live),true);
 if(hash(liveFile)!==hashBytes(new java.lang.String(String(live)).getBytes(UTF)))throw Error('Live backup hash mismatch');
 var report={time:new Date().toISOString(),status:'preflight',machineState:startState,deviceById:port,resolvedDevice:resolved,previousPort:oldPort,driverId:String(d.getId()),driverJarSha256:hash(jar),connectCommands:PasteConnectionPolicy.tokens(connect),connectSideEffects:'G21 millimeters, G90 absolute mode, M260 VAC sensor initialization; no movement/enable/home commands. USB connection may reset controller; homing remains invalid.',backup:String(backup),diskMachineSha256:diskHash,liveBackupSha256:hash(liveFile),queries:[],noAutomaticRetry:true,physicalVerification:false,persistence:'No cfg.save; normal app exit can persist in-memory port change. Reinspect after restart.'};
 function save(){write(new F(evidence,'report.json'),JSON.stringify(report,null,2)+'\n',false);}
 save();
 var connectionAttempted=false;
 try{
  auditState();noOwner();
  // Audited model setter only. Preserve all other serial and machine settings.
  serial.setPortName(port);if(String(serial.getPortName())!==port)throw Error('Port setter verification failed');
  report.status='port-updated-in-memory';save();
  auditState();noOwner();PasteConnectionPolicy.checkCommands(d.getCommand(null,CT.CONNECT_COMMAND),d.getCommand(null,CT.ENABLE_COMMAND),d.getCommand(null,CT.DISABLE_COMMAND));
  connectionAttempted=true;report.status='connecting-native-owner';save();d.connect();
  if(!(String(privateValue(GD,'connected',d))==='true')||m.isEnabled()||m.isHomed())throw Error('Unexpected state after native connect');
  report.status='connected-disabled-unhomed';report.connectResponses=[];
  for each(var line in d.receiveResponses())report.connectResponses.push(String(line.getLine()));save();PasteConnectionPolicy.responses(report.connectResponses);
  for each(var command in ['M115','M503']){
   if(m.isEnabled()||m.isHomed())throw Error('Machine state changed during inspection');
   var q={command:command,status:'sent',responses:[]};report.queries.push(q);save();
   d.sendCommand(command,3000);
   for each(var response in d.receiveResponses())q.responses.push(String(response.getLine()));
   PasteConnectionPolicy.responses(q.responses);q.status='acknowledged';save();
  }
  var identity=report.queries[0].responses.join('\n'),settings=report.queries[1].responses.join('\n');
  if(!/FIRMWARE_NAME:.*Marlin/.test(identity)||!/MACHINE_TYPE:LumenPnP/.test(identity)||!/AXIS_COUNT:5/.test(identity))throw Error('Unrecognized/absent live firmware identity; inspect captured responses');
  if(!/M92\s/.test(settings))throw Error('M503 did not capture expected settings payload; ACK alone is insufficient');
  report.status='queried-native-owner';
 }catch(e){report.status='failed-no-retry';report.error=String(e);throw e;}
 finally{
  if(connectionAttempted){try{
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
