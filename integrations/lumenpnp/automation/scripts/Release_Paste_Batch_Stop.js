// STAGED MODEL-ONLY release of one independently audited partial batch stop.
// No query, motion, completion, serial operation, config save or survey replay.
(function(){
 var C=Java.type('org.openpnp.model.Configuration'),F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8,
 MD=Java.type('java.security.MessageDigest'),AL=Java.type('org.openpnp.model.AxesLocation'),MM=Java.type('org.openpnp.model.LengthUnit').Millimeters;
 var root='/home/lumen/lumenpnp/',id='9d2592a4-0b68-41a7-ba1a-4fa1e7b40bc9',faultHash='5bf33a41606c386994847603586cb50bcd2209556d5b49f5137b705495430f08',auditHash='3d8c903c3afd58ba86f39bfb609452fdc0685c2f5b5b22a1f3e331b39d001adc';
 function bytes(s){return new java.lang.String(s).getBytes(UTF);}
 function hash(b){var a=MD.getInstance('SHA-256').digest(b),s='';for(var i=0;i<a.length;i++)s+=('0'+((a[i]&255).toString(16))).slice(-2);return s;}
 function verified(path,expected){var b=Fs.readAllBytes(new F(path).toPath());if(hash(b)!==expected)throw Error('Reviewed artifact changed: '+path);return JSON.parse(String(new java.lang.String(b,UTF)));}
 function field(c,n){var f=Java.type(c).class.getDeclaredField(n);f.setAccessible(true);return f;}
 function close(a,b,label){if(typeof a!=='number'||typeof b!=='number'||!isFinite(a)||!isFinite(b)||Math.abs(a-b)>0.0001)throw Error(label+' changed');}
 var fault=verified(root+'automation/evidence/paste-contiguous-batch-'+id+'/report.json',faultHash),audit=verified(root+'automation/evidence/paste-batch-stop-audit-'+id+'/report.json',auditHash);
 var batchGross=fault.request.previewStages.reduce(function(n,st){return n+(st.axis==='B'?Math.abs(st.targetRaw.B-st.startRaw.B):0);},0); if(batchGross!==239)throw Error('The exact batch reservation is not 239 degrees');
 if(audit.faultId!==id||audit.faultSha256!==faultHash||audit.status!=='audit-complete-awaiting-separate-reviewed-latch-clear'||audit.positionVerified!==true||audit.stationaryImagesCaptured!==true||audit.latchCleared!==false||audit.motionIssued!==false||audit.verifiedPartialStop!==true||audit.completedStageCount!==52||audit.lastVerifiedStageIndex!==51||audit.lastVerifiedB!==-3174||fault.status!=='stopped-contiguous-batch-no-retry'||fault.stages.length!==52||fault.stages.some(function(s,i){return s.index!==i||s.verified!==true||s.nativeMotionCompletionReported!==true;})||fault.stages[51].axis!=='B'||fault.stages[51].targetRaw.B!==-3174||fault.uncertainCompletion!==false||fault.transportUncertain!==false||fault.controllerPositionVerified!==true||fault.executorQuarantined!==true||fault.queuedTasksCancelled!==0||fault.reservedAbsoluteDegrees!==8967||fault.ledgerPath==null)throw Error('Not the reviewed completed partial-batch audit');
 if(Number(java.lang.System.currentTimeMillis())-Date.parse(audit.finishedAt)>300000)throw Error('Fresh audit expired');
 if(!Java.type('javax.swing.SwingUtilities').isEventDispatchThread())throw Error('Use the reviewed EDT dispatcher for this short model-only release');
 var m=C.get().getMachine(),planner=m.getMotionPlanner(),jvm=Number(Java.type('java.lang.management.ManagementFactory').getRuntimeMXBean().getStartTime());
 if(jvm!==audit.jvmStartMs||jvm!==fault.request.jvmStartMs||m.getDrivers().size()!==1)throw Error('Session changed');
 var d=m.getDrivers().get(0),exField=field('org.openpnp.spi.base.AbstractMachine','executor'),ownerField=field('org.openpnp.spi.base.AbstractMachine','taskThread'),oldEx=exField.get(m),oldOwner=ownerField.get(m);
 if(String(d.getClass().getName())!=='org.openpnp.machine.reference.driver.GcodeDriver'||String(d.getId())!=='DRV16982438146c1dd4'||String(planner.getClass().getName())!=='org.openpnp.machine.reference.driver.NullMotionPlanner')throw Error('Native owner changed');
 var jar=new F(d.getClass().getProtectionDomain().getCodeSource().getLocation().toURI());if(hash(Fs.readAllBytes(jar.toPath()))!=='bcd34923ae91d61a96b98b4c82c93cdc90093ff94292270fd0a18fc6f96f7752')throw Error('Native API changed');
 function configHash(){var w=new java.io.StringWriter();C.createSerializer().write(m,w);return hash(bytes(String(w)));}
 var head=m.getDefaultHead(),right=head.getNozzleByName('N2'),left=head.getNozzleByName('N1'),top=head.getDefaultCamera(),bottom=null;
 for each(var cam in m.getCameras())if(String(cam.getLooking())==='Up'){if(bottom!==null)throw Error('Ambiguous bottom camera');bottom=cam;}
 if(right==null||left==null||top==null||bottom==null||String(right.getId())!=='NOZ1710829fd33a0170')throw Error('Head changed');
 var panel=Java.type('org.openpnp.gui.MainFrame').get().getJobTab(),state=panel.getClass().getDeclaredField('state');state.setAccessible(true);
 function snapshot(){var s={raw:{},driver:{},nativePoses:{}};for each(var a in new AL(m).drivenBy(d).getControllerAxes()){var k=String(a.getLetter());if(s.raw.hasOwnProperty(k))throw Error('Duplicate axis');s.raw[k]=Number(a.getCoordinate());s.driver[k]=Number(a.getDriverCoordinate());}var all={N1:left,N2:right,top:top,bottom:bottom};Object.keys(all).forEach(function(k){var p=all[k].getLocation().convertToUnits(MM);s.nativePoses[k]={x:Number(p.getX()),y:Number(p.getY()),z:Number(p.getZ()),rotation:Number(p.getRotation())};});return s;}
 function same(s){if(Object.keys(s.raw).sort().join(',')!=='A,B,X,Y,Z')throw Error('Raw axes changed');['raw','driver'].forEach(function(kind){['X','Y','Z','A','B'].forEach(function(k){close(s[kind][k],audit.afterQuerySnapshot[kind][k],kind+' '+k);});});['N1','N2','top','bottom'].forEach(function(k){['x','y','z','rotation'].forEach(function(a){close(s.nativePoses[k][a],audit.afterQuerySnapshot.nativePoses[k][a],k+' '+a);});});}
 function gate(){
  if(!m.isBusy()||!m.isEnabled()||!m.isHomed()||String(state.get(panel))!=='Stopped')throw Error('Latched machine state changed');
  if(oldEx==null||!oldEx.isShutdown()||!oldEx.isTerminated()||oldEx.getActiveCount()!==0||!oldEx.getQueue().isEmpty()||oldOwner==null||oldOwner.isAlive()||exField.get(m)!==oldEx||ownerField.get(m)!==oldOwner)throw Error('Expected dead owner and terminated empty executor');
  if(String(field('org.openpnp.machine.reference.driver.GcodeDriver','connected').get(d))!=='true'||d.isMotionPending()||field('org.openpnp.machine.reference.driver.AbstractMotionPlanner','motionCommands').get(planner).size()!==0)throw Error('Driver changed or motion pending');
  if(right.getNozzleTip()!=null||right.getCompatibleNozzleTips().size()!==0||right.getRotationModeOffset()!=null||right.isChangerEnabled()||m.getPnpJobProcessor().isPreRotateAllNozzles())throw Error('Quarantine changed');
  var reader=field('org.openpnp.machine.reference.driver.GcodeDriver','readerThread').get(d);if(reader==null||!reader.isAlive()||field('org.openpnp.machine.reference.driver.GcodeDriver','errorResponse').get(d)!=null||d.isInSimulationMode())throw Error('Reader fault/simulation');
  if(hash(Fs.readAllBytes(new F(fault.ledgerPath).toPath()))!==audit.ledgerSha256)throw Error('Faulted ledger changed');
  if(configHash()!==audit.liveConfigurationSha256)throw Error('Live configuration changed');same(snapshot());
 }
 gate();
 var out=new F(root+'automation/evidence/paste-batch-stop-release-'+id);if(!out.mkdir())throw Error('Release already claimed; no retry');
 var r={schema:1,scope:'model-only-specific-pre-dose-batch-stop-release',faultId:id,faultSha256:faultHash,auditSha256:auditHash,jvmStartMs:jvm,startedAt:new Date().toISOString(),before:snapshot(),latchCleared:false,queryIssued:false,motionIssued:false,replayIssued:false,configurationSaved:false,ledgerModified:false,faultedLedgerSha256:audit.ledgerSha256};
 function save(status){r.status=status;Fs.write(new F(out,'report.json').toPath(),bytes(JSON.stringify(r,null,2)+'\n'));}
 save('validated-before-model-release');
 var fresh=null,changed=false;
 try{
  // Exact constructor from installed AbstractMachine.submit bytecode. Constructing
  // this executor starts no worker; no task is submitted by this script.
  fresh=new (Java.type('java.util.concurrent.ThreadPoolExecutor'))(1,1,1,Java.type('java.util.concurrent.TimeUnit').SECONDS,new (Java.type('java.util.concurrent.LinkedBlockingQueue'))());
  if(fresh.getPoolSize()!==0||fresh.getActiveCount()!==0||!fresh.getQueue().isEmpty())throw Error('Replacement executor unexpectedly active');
  gate();exField.set(m,fresh);changed=true;ownerField.set(m,null);m.fireMachineBusy(false);
  if(m.isBusy()||exField.get(m)!==fresh||ownerField.get(m)!==null||fresh.isShutdown()||fresh.getPoolSize()!==0||!fresh.getQueue().isEmpty())throw Error('Release postcheck failed');
  same(snapshot());if(configHash()!==audit.liveConfigurationSha256)throw Error('Configuration changed during release');
  r.after=snapshot();r.replacementPoolSize=fresh.getPoolSize();r.latchCleared=true;r.finishedAt=new Date().toISOString();save('model-release-complete-no-motion-no-replay');
 }catch(e){
  r.error=String(e);if(changed){ownerField.set(m,oldOwner);exField.set(m,oldEx);try{m.fireMachineBusy(true);}catch(notifyError){r.notificationError=String(notifyError);}}if(fresh!==null)fresh.shutdown();r.latchCleared=false;r.finishedAt=new Date().toISOString();save('release-failed-old-latch-restored');throw e;
 }
 print(String(out));
})();
