// Reviewed two-field in-memory change only. No controller command or coordinate reset.
(function(){
 var C=Java.type('org.openpnp.model.Configuration'),F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8,
 L=Java.type('org.openpnp.model.Length'),MD=Java.type('java.security.MessageDigest'),CT=Java.type('org.openpnp.machine.reference.driver.GcodeDriver$CommandType'),AL=Java.type('org.openpnp.model.AxesLocation'),MM=Java.type('org.openpnp.model.LengthUnit').Millimeters;
 var root='/home/lumen/lumenpnp/',cfg=C.get(),m=cfg.getMachine(),planner=m.getMotionPlanner();
 function bytes(s){return new java.lang.String(s).getBytes(UTF);}
 function read(p){return String(new java.lang.String(Fs.readAllBytes(new F(p).toPath()),UTF));}
 function hash(data){var a=MD.getInstance('SHA-256').digest(data),s='';for(var i=0;i<a.length;i++)s+=('0'+((a[i]&255).toString(16))).slice(-2);return s;}
 function privateValue(cls,name,obj){var f=Java.type(cls).class.getDeclaredField(name);f.setAccessible(true);return f.get(obj);}
 function serialized(){var w=new java.io.StringWriter();C.createSerializer().write(m,w);return String(w);}
 eval(read(root+'automation/paste/native-air.cjs'));eval(read(root+'automation/paste/b-axis-configuration.cjs'));eval(read(root+'automation/paste/z-observation.cjs'));
 var q=JSON.parse(read(root+'automation/plans/paste-b-axis-configuration-request.json')),jvm=Number(Java.type('java.lang.management.ManagementFactory').getRuntimeMXBean().getStartTime());
 function validate(){PasteBConfiguration.validate(q,Number(java.lang.System.currentTimeMillis()),jvm);PasteZObservation.barrier(barrier,q,Number(java.lang.System.currentTimeMillis()));}
 PasteBConfiguration.validate(q,Number(java.lang.System.currentTimeMillis()),jvm);
 var barrierBytes=Fs.readAllBytes(new F(q.barrierEvidence.path).toPath());if(hash(barrierBytes)!==q.barrierEvidence.sha256)throw Error('Barrier bytes changed');var barrier=JSON.parse(String(new java.lang.String(barrierBytes,UTF)));validate();
 var panel=Java.type('org.openpnp.gui.MainFrame').get().getJobTab(),state=panel.getClass().getDeclaredField('state');state.setAccessible(true);
 if(m.getDrivers().size()!==1)throw Error('Unexpected driver topology');var d=m.getDrivers().get(0);
 if(String(d.getClass().getName())!=='org.openpnp.machine.reference.driver.GcodeDriver'||String(d.getId())!=='DRV16982438146c1dd4'||String(planner.getClass().getName())!=='org.openpnp.machine.reference.driver.NullMotionPlanner')throw Error('Unknown native owner/planner');
 var jar=new F(d.getClass().getProtectionDomain().getCodeSource().getLocation().toURI());if(hash(Fs.readAllBytes(jar.toPath()))!=='bcd34923ae91d61a96b98b4c82c93cdc90093ff94292270fd0a18fc6f96f7752')throw Error('Installed native API changed');
 var head=m.getDefaultHead(),n1=head.getNozzleByName('N1'),n2=head.getNozzleByName('N2'),top=head.getDefaultCamera(),bottom=null,axes={};
 for each(var camera in m.getCameras())if(String(camera.getLooking())==='Up'){if(bottom!==null)throw Error('Multiple bottom cameras');bottom=camera;}
 if(n1==null||String(n1.getId())!=='N1'||n2==null||String(n2.getId())!=='NOZ1710829fd33a0170'||top==null||String(top.getId())!=='CAM1607555396816'||bottom==null)throw Error('Unexpected native head/camera identities');
 for each(var a in new AL(m).drivenBy(d).getControllerAxes()){var letter=String(a.getLetter());if(axes[letter])throw Error('Duplicate axis');axes[letter]=a;}
 if(Object.keys(axes).sort().join(',')!=='A,B,X,Y,Z'||String(axes.B.getId())!=='AXS17108288e61da5fb'||String(axes.B.getType())!=='Rotation')throw Error('Unexpected B/controller axes');
 var executor=privateValue('org.openpnp.spi.base.AbstractMachine','executor',m),reader=privateValue('org.openpnp.machine.reference.driver.GcodeDriver','readerThread',d),commands=d.commands,items={N1:n1,N2:n2,top:top,bottom:bottom};
 function snapshot(){var r={raw:{},driver:{},nativePoses:{}};Object.keys(axes).forEach(function(k){r.raw[k]=Number(axes[k].getCoordinate());r.driver[k]=Number(axes[k].getDriverCoordinate());});Object.keys(items).forEach(function(k){var p=items[k].getLocation().convertToUnits(MM);r.nativePoses[k]={x:Number(p.getX()),y:Number(p.getY()),z:Number(p.getZ()),rotation:Number(p.getRotation())};});return r;}
 function checkSnapshot(s){PasteZObservation.compareExact(s.raw,q.expectedRaw,'raw start');PasteZObservation.compareExact(s.driver,q.expectedDriver,'driver start');Object.keys(items).forEach(function(k){['x','y','z','rotation'].forEach(function(a){PasteZObservation.close(s.nativePoses[k][a],q.expectedNativePoses[k][a],.0001,'native start '+k+' '+a);});});}
 function gate(){
  if((m.isBusy()&&!m.isTask(java.lang.Thread.currentThread()))||String(state.get(panel))!=='Stopped'||executor==null||privateValue('org.openpnp.spi.base.AbstractMachine','executor',m)!==executor||executor.isShutdown()||executor.isTerminated()||executor.getCorePoolSize()!==1||executor.getMaximumPoolSize()!==1||!executor.getQueue().isEmpty())throw Error('Need idle existing single-worker native owner');
  if(!m.isTask(java.lang.Thread.currentThread())&&executor.getActiveCount()!==0)throw Error('Native worker active');
  if(reader==null||!reader.isAlive()||privateValue('org.openpnp.machine.reference.driver.GcodeDriver','readerThread',d)!==reader||d.commands!==commands||String(privateValue('org.openpnp.machine.reference.driver.GcodeDriver','connected',d))!=='true'||privateValue('org.openpnp.machine.reference.driver.GcodeDriver','errorResponse',d)!=null||d.isMotionPending())throw Error('Reader/driver state changed');
  if(privateValue('org.openpnp.machine.reference.driver.AbstractMotionPlanner','motionCommands',planner).size()!==0)throw Error('Queued native motion');
  var sub=privateValue('org.openpnp.machine.reference.driver.AbstractMotionPlanner','subordinateMotion',planner),queue=privateValue('org.openpnp.machine.reference.driver.AbstractMotionPlanner$SubordinateMotion','queue',sub);if(queue!=null&&!queue.isEmpty())throw Error('Queued subordinate axes');
  if(n2.getNozzleTip()!=null||n2.getCompatibleNozzleTips().size()!==0||n2.getRotationModeOffset()!=null||n2.isChangerEnabled()||n2.getManualNozzleTipChangeLocation().isInitialized()||m.getPnpJobProcessor().isPreRotateAllNozzles())throw Error('N2 quarantine changed');
  for each(var h in m.getHeads())for each(var n in h.getNozzles())if(n.getPart()!=null||n.getPartsFeeder()!=null)throw Error('Held/associated part');
  if(String(d.getCommand(null,CT.COMMAND_ERROR_REGEX))!==NativePasteAir.nativeErrorRegex)throw Error('Reviewed error latch changed');
  if(axes.B.isWrapAroundRotation())throw Error('B wrap must remain disabled');
 }
 var originalFeed=axes.B.getFeedratePerSecond();if(originalFeed.getUnits()!==MM||Number(originalFeed.getValue())!==50000)throw Error('Unexpected legacy B feedrate');
 gate();checkSnapshot(snapshot());if(hash(bytes(serialized()))!==q.liveConfigurationSha256||!axes.B.isLimitRotation())throw Error('Configuration/prior B flag differs');
 var backupRoot=new F(root+'.local-machine-backups');if(!backupRoot.isDirectory())throw Error('Private backup root missing');var out=new F(backupRoot,'paste-b-axis-configuration-'+q.id);if(!out.mkdir())throw Error('UUID already claimed; no replay');
 function write(name,data){Fs.write(new F(out,name).toPath(),data);}
 var report={schema:1,id:q.id,request:q,status:'claimed',previousLimitRotation:true,requestedLimitRotation:false,previousFeedratePerSecond:50000,requestedFeedratePerSecond:100,nominalFraction005SpeedUnitsPerSecond:5,noControllerCommands:true,configurationSaved:false,extrusionAuthorized:false,installedRegex:NativePasteAir.nativeErrorRegex};
 function save(status){report.status=status;write('report.json',bytes(JSON.stringify(report,null,2)+'\n'));}save('queued-existing-native-worker');
 var setter=Java.type('org.openpnp.spi.base.AbstractMachine').class.getDeclaredMethod('setTaskThread',Java.type('java.lang.Thread').class);setter.setAccessible(true);
 function owner(thread){setter.invoke(m,Java.to([thread],'java.lang.Object[]'));}
 try{executor.submit(new (Java.type('java.util.concurrent.Callable'))({call:function(){var owned=false,changed=false,keepBusy=false,before=null,expected=null;
  try{
   if(m.isBusy()||!executor.getQueue().isEmpty())throw Error('Native ownership changed');owner(java.lang.Thread.currentThread());owned=true;m.fireMachineBusy(true);
   validate();gate();report.beforeSnapshot=snapshot();checkSnapshot(report.beforeSnapshot);before=serialized();if(hash(bytes(before))!==q.liveConfigurationSha256||!axes.B.isLimitRotation())throw Error('Configuration changed');expected=PasteBConfiguration.expectedXml(before);
   var disk=new F(cfg.getConfigurationDirectory(),'machine.xml'),diskBytes=Fs.readAllBytes(disk.toPath());if(hash(diskBytes)!==q.diskMachineSha256)throw Error('Disk configuration changed');write('disk-machine-before.xml',diskBytes);write('live-machine-before.xml',bytes(before));
   if(hash(Fs.readAllBytes(new F(out,'disk-machine-before.xml').toPath()))!==q.diskMachineSha256||hash(Fs.readAllBytes(new F(out,'live-machine-before.xml').toPath()))!==q.liveConfigurationSha256)throw Error('Backup verification failed');save('verified-backups-before-two-field-change');
   validate();gate();checkSnapshot(snapshot());if(serialized()!==before)throw Error('Concurrent configuration change');
   axes.B.setLimitRotation(false);changed=true;axes.B.setFeedratePerSecond(new L(100,MM));
   var after=serialized();if(after!==expected||axes.B.isLimitRotation()||axes.B.isWrapAroundRotation())throw Error('More than the two intended B fields changed');
   gate();report.afterSnapshot=snapshot();checkSnapshot(report.afterSnapshot);write('live-machine-after.xml',bytes(after));report.liveConfigurationAfterSha256=hash(bytes(after));
   if(hash(Fs.readAllBytes(new F(out,'live-machine-after.xml').toPath()))!==report.liveConfigurationAfterSha256||hash(Fs.readAllBytes(disk.toPath()))!==q.diskMachineSha256)throw Error('After backup/disk verification failed');
   report.diskUnchanged=true;report.coordinatesUnchanged=true;report.exactTwoFieldChangeVerified=true;save('configured-B-prerequisites-in-memory-awaiting-fresh-barrier');
  }catch(e){
   report.error=String(e);
   if(changed){
    try{var current=serialized(),flagOnly=before.replace(/<axis\b[^>]*\bid="AXS17108288e61da5fb"[^>]*>/,function(tag){return tag.replace('limit-rotation="true"','limit-rotation="false"');});
     if((current===expected||current===flagOnly)&&!axes.B.isLimitRotation()){axes.B.setFeedratePerSecond(originalFeed);axes.B.setLimitRotation(true);report.rollbackVerified=serialized()===before;}else report.rollbackRefusedConcurrentChange=true;
    }catch(rollbackError){report.rollbackError=String(rollbackError);}
    if(report.rollbackVerified!==true){keepBusy=true;executor.shutdown();report.executorQuarantined=true;}
   }
   save('failed-no-controller-commands-no-retry');
  }finally{if(owned&&!keepBusy){owner(null);m.fireMachineBusy(false);}print(String(out));}return null;
 }}));}catch(e){report.error=String(e);save('enqueue-failed-no-change');throw e;}
})();
