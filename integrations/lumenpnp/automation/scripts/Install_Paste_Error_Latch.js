// STAGED no-motion in-memory configuration change. No save, query, connect or actuation.
// A reviewed request is mandatory; parent alone dispatches after source review.
(function(){
 var C=Java.type('org.openpnp.model.Configuration'),F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8,
 MD=Java.type('java.security.MessageDigest'),CT=Java.type('org.openpnp.machine.reference.driver.GcodeDriver$CommandType'),Command=Java.type('org.openpnp.machine.reference.driver.GcodeDriver$Command');
 var root='/home/lumen/lumenpnp/',cfg=C.get(),m=cfg.getMachine(),planner=m.getMotionPlanner();
 function bytes(s){return new java.lang.String(s).getBytes(UTF);}
 function read(p){return String(new java.lang.String(Fs.readAllBytes(new F(p).toPath()),UTF));}
 function hash(data){var a=MD.getInstance('SHA-256').digest(data),s='';for(var i=0;i<a.length;i++)s+=('0'+((a[i]&255).toString(16))).slice(-2);return s;}
 function privateValue(cls,name,obj){var f=Java.type(cls).class.getDeclaredField(name);f.setAccessible(true);return f.get(obj);}
 function serialized(){var w=new java.io.StringWriter();C.createSerializer().write(m,w);return String(w);}
 eval(read(root+'automation/paste/native-air.cjs'));eval(read(root+'automation/paste/error-latch-install.cjs'));
 var q=JSON.parse(read(root+'automation/plans/paste-error-latch-request.json')),jvm=Number(Java.type('java.lang.management.ManagementFactory').getRuntimeMXBean().getStartTime());
 PasteErrorLatchInstall.validate(q,Number(java.lang.System.currentTimeMillis()),jvm);
 var panel=Java.type('org.openpnp.gui.MainFrame').get().getJobTab(),state=panel.getClass().getDeclaredField('state');state.setAccessible(true);
 if(m.getDrivers().size()!==1)throw Error('Unexpected driver topology');var d=m.getDrivers().get(0);
 if(String(d.getClass().getName())!=='org.openpnp.machine.reference.driver.GcodeDriver'||String(d.getId())!=='DRV16982438146c1dd4'||String(planner.getClass().getName())!=='org.openpnp.machine.reference.driver.NullMotionPlanner')throw Error('Unknown native owner/planner');
 var jar=new F(d.getClass().getProtectionDomain().getCodeSource().getLocation().toURI());if(hash(Fs.readAllBytes(jar.toPath()))!=='bcd34923ae91d61a96b98b4c82c93cdc90093ff94292270fd0a18fc6f96f7752')throw Error('Installed native API changed');
 var n2=m.getDefaultHead().getNozzleByName('N2'),executor=privateValue('org.openpnp.spi.base.AbstractMachine','executor',m);
 var originalReader=privateValue('org.openpnp.machine.reference.driver.GcodeDriver','readerThread',d);
 function coordinates(){var result={};for each(var axis in new (Java.type('org.openpnp.model.AxesLocation'))(m).drivenBy(d).getControllerAxes())result[String(axis.getId())]={model:Number(axis.getCoordinate()),driver:Number(axis.getDriverCoordinate())};return JSON.stringify(result);}
 function gate(){
  if(privateValue('org.openpnp.spi.base.AbstractMachine','executor',m)!==executor||m.isBusy()||String(state.get(panel))!=='Stopped'||executor==null||executor.isShutdown()||executor.isTerminated()||executor.getCorePoolSize()!==1||executor.getMaximumPoolSize()!==1||executor.getActiveCount()!==0||!executor.getQueue().isEmpty())throw Error('Need idle native single-worker owner and stopped job');
  if(String(privateValue('org.openpnp.machine.reference.driver.GcodeDriver','connected',d))!=='true'||d.isMotionPending())throw Error('Owner disconnected or motion pending');
  if(privateValue('org.openpnp.machine.reference.driver.AbstractMotionPlanner','motionCommands',planner).size()!==0)throw Error('Native motion queued');
  var sub=privateValue('org.openpnp.machine.reference.driver.AbstractMotionPlanner','subordinateMotion',planner),queue=privateValue('org.openpnp.machine.reference.driver.AbstractMotionPlanner$SubordinateMotion','queue',sub);if(queue!=null&&!queue.isEmpty())throw Error('Subordinate axes queued');
  var reader=privateValue('org.openpnp.machine.reference.driver.GcodeDriver','readerThread',d);if(reader==null||reader!==originalReader||!reader.isAlive())throw Error('Native reader not alive');
  if(privateValue('org.openpnp.machine.reference.driver.GcodeDriver','errorResponse',d)!=null)throw Error('Existing fault must not be cleared');
  if(n2==null||String(n2.getId())!=='NOZ1710829fd33a0170'||n2.getNozzleTip()!=null||n2.getCompatibleNozzleTips().size()!==0||n2.getRotationModeOffset()!=null||n2.isChangerEnabled()||n2.getManualNozzleTipChangeLocation().isInitialized()||m.getPnpJobProcessor().isPreRotateAllNozzles())throw Error('N2 quarantine changed');
  for each(var h in m.getHeads())for each(var n in h.getNozzles())if(n.getPart()!=null||n.getPartsFeeder()!=null)throw Error('Held/associated part');
 }
 gate();
 if(d.getCommand(null,CT.COMMAND_ERROR_REGEX)!=null)throw Error('Error regex already present; no replacement or replay');
 for each(var command in d.commands)if(command.type===CT.COMMAND_ERROR_REGEX)throw Error('Unexpected scoped/empty error command');
 var disk=new F(cfg.getConfigurationDirectory(),'machine.xml'),diskBytes=Fs.readAllBytes(disk.toPath()),before=serialized();
 if(hash(diskBytes)!==q.diskMachineSha256||hash(bytes(before))!==q.liveConfigurationSha256)throw Error('Bound configuration changed');
 var backupRoot=new F(root+'.local-machine-backups');if(!backupRoot.isDirectory())throw Error('Private backup root missing');
 var out=new F(backupRoot,'paste-error-latch-'+q.id);if(!out.mkdir())throw Error('UUID already claimed; no replay');
 function write(name,data){Fs.write(new F(out,name).toPath(),data);}
 write('disk-machine-before.xml',diskBytes);write('live-machine-before.xml',bytes(before));
 if(hash(Fs.readAllBytes(new F(out,'disk-machine-before.xml').toPath()))!==q.diskMachineSha256||hash(Fs.readAllBytes(new F(out,'live-machine-before.xml').toPath()))!==q.liveConfigurationSha256)throw Error('Backup verification failed');
 var beforeCoordinates=coordinates();
 var original=d.commands,replacement=new java.util.ArrayList(original);replacement.add(new Command(null,CT.COMMAND_ERROR_REGEX,NativePasteAir.nativeErrorRegex));
 var report={schema:1,id:q.id,request:q,status:'backed-up-before-mutation',previousCommand:null,installedRegex:NativePasteAir.nativeErrorRegex,noControllerCommands:true,configurationSaved:false,readerFaultInjectionTested:false,publication:'Copy-on-write complete command list; native public reference is nonvolatile. Later separate read-only position barrier and activation review required.'};
 function save(){write('report.json',bytes(JSON.stringify(report,null,2)+'\n'));}save();
 var published=false;
 try{
  gate();PasteErrorLatchInstall.validate(q,Number(java.lang.System.currentTimeMillis()),jvm);
  if(d.commands!==original||hash(bytes(serialized()))!==q.liveConfigurationSha256||hash(Fs.readAllBytes(disk.toPath()))!==q.diskMachineSha256)throw Error('State changed before publication');
  // Do not mutate the list an asynchronous reader may already be iterating.
  d.commands=replacement;published=true;
  if(String(d.getCommand(null,CT.COMMAND_ERROR_REGEX))!==NativePasteAir.nativeErrorRegex)throw Error('Native regex readback mismatch');
  gate();var after=serialized();report.liveConfigurationAfterSha256=hash(bytes(after));write('live-machine-after.xml',bytes(after));if(hash(Fs.readAllBytes(new F(out,'live-machine-after.xml').toPath()))!==report.liveConfigurationAfterSha256)throw Error('After-live backup verification failed');
  if(hash(Fs.readAllBytes(disk.toPath()))!==q.diskMachineSha256)throw Error('Disk configuration changed unexpectedly');
  if(coordinates()!==beforeCoordinates)throw Error('Coordinates changed during configuration edit');report.coordinatesUnchanged=true;
  report.diskUnchanged=true;report.status='installed-in-memory-awaiting-read-only-barrier-and-review';save();
 }catch(e){
  report.error=String(e);if(published&&d.commands===replacement){d.commands=original;report.originalListRestored=true;report.rollbackLiveHash=hash(bytes(serialized()));}else if(published)report.rollbackRefusedConcurrentChange=true;
  report.status='failed-no-controller-commands';save();throw e;
 }
 print(String(out));
})();
