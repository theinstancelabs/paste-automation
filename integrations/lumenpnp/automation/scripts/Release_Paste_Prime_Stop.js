// Release one independently audited B-prime timeout using fixed native M400 only.
// No movement, generic planner completion, serial reconnect, config save or replay.
(function(){
 var C=Java.type('org.openpnp.model.Configuration'),F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8,
 MD=Java.type('java.security.MessageDigest'),AL=Java.type('org.openpnp.model.AxesLocation'),MM=Java.type('org.openpnp.model.LengthUnit').Millimeters;
 var root='/home/lumen/lumenpnp/',id='ba7bf3db-7458-47e4-9e80-d9f90df6ac89',faultHash='e68ca2c1f912d41bbabb06a8664941e90f480f354d6f3063fe99b56bbed79032',auditHash='f20f9d79ee9cd5d1a2d2accba36e9e3565a15845032f68fe82f8d597fddd0479';
 function bytes(s){return new java.lang.String(s).getBytes(UTF);}
 function hash(b){var a=MD.getInstance('SHA-256').digest(b),s='';for(var i=0;i<a.length;i++)s+=('0'+((a[i]&255).toString(16))).slice(-2);return s;}
 function verified(path,expected){var b=Fs.readAllBytes(new F(path).toPath());if(hash(b)!==expected)throw Error('Reviewed artifact changed: '+path);return JSON.parse(String(new java.lang.String(b,UTF)));}
 function field(c,n){var f=Java.type(c).class.getDeclaredField(n);f.setAccessible(true);return f;}
 function close(a,b,label){if(typeof a!=='number'||typeof b!=='number'||!isFinite(a)||!isFinite(b)||Math.abs(a-b)>0.0001)throw Error(label+' changed');}
 var fault=verified(root+'automation/evidence/paste-waste-prime-'+id+'/report.json',faultHash),audit=verified(root+'automation/evidence/paste-prime-stop-audit-'+id+'/report.json',auditHash);
 if(audit.faultId!==id||audit.faultSha256!==faultHash||audit.status!=='audit-complete-awaiting-separate-reviewed-latch-clear'||audit.positionVerified!==true||audit.stationaryImagesCaptured!==true||audit.latchCleared!==false||audit.motionIssued!==false||audit.countsVerified!==true||audit.lateCompletionAckObserved!==true||fault.uncertainCompletion!==true||fault.expectedAfterRaw.B!==280)throw Error('Not the reviewed completed audit');
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
 var reader=field('org.openpnp.machine.reference.driver.GcodeDriver','readerThread').get(d);
 var expectedPending=true;
 function gate(){
  if(reader==null||!reader.isAlive()||field('org.openpnp.machine.reference.driver.GcodeDriver','readerThread').get(d)!==reader||field('org.openpnp.machine.reference.driver.GcodeDriver','errorResponse').get(d)!=null)throw Error('Native reader/error state changed');
  if(!m.isBusy()||!m.isEnabled()||!m.isHomed()||String(state.get(panel))!=='Stopped')throw Error('Latched machine state changed');
  if(oldEx==null||!oldEx.isShutdown()||!oldEx.isTerminated()||oldEx.getActiveCount()!==0||!oldEx.getQueue().isEmpty()||oldOwner==null||oldOwner.isAlive()||exField.get(m)!==oldEx||ownerField.get(m)!==oldOwner)throw Error('Expected dead owner and terminated empty executor');
  if(String(field('org.openpnp.machine.reference.driver.GcodeDriver','connected').get(d))!=='true'||d.isMotionPending()!==expectedPending||field('org.openpnp.machine.reference.driver.AbstractMotionPlanner','motionCommands').get(planner).size()!==0)throw Error('Driver changed or motion pending');
  if(right.getNozzleTip()!=null||right.getCompatibleNozzleTips().size()!==0||right.getRotationModeOffset()!=null||right.isChangerEnabled()||m.getPnpJobProcessor().isPreRotateAllNozzles())throw Error('Quarantine changed');
  if(configHash()!==audit.liveConfigurationSha256)throw Error('Live configuration changed');same(snapshot());
 }
 var ledgerPath=root+'automation/evidence/paste-waste-prime-session/ledger.json',ledgerHash='23993cbaee62c21be624b8215b1668ab53b8cfc469a37282f79ef6032e539f07',ledger=verified(ledgerPath,ledgerHash),last=ledger.entries[ledger.entries.length-1];
 if(ledger.status!=='faulted'||ledger.reservedDegrees!==440||ledger.lastVerifiedB!==380||last.requestId!==id||last.status!=='faulted'||last.reservedDegrees!==100||last.startB!==380||last.targetB!==280||ledger.profileSha256!==fault.request.profileEvidence.sha256)throw Error('Charged fault ledger changed');
 gate();
 var out=new F(root+'automation/evidence/paste-prime-stop-release-'+id);if(!out.mkdir())throw Error('Release already claimed; no retry');
 var r={schema:1,scope:'audited-prime-stop-completion-and-release',faultId:id,faultSha256:faultHash,auditSha256:auditHash,jvmStartMs:jvm,startedAt:new Date().toISOString(),before:snapshot(),latchCleared:false,queryIssued:false,motionIssued:false,replayIssued:false,configurationSaved:false};
 function save(status){r.status=status;Fs.write(new F(out,'report.json').toPath(),bytes(JSON.stringify(r,null,2)+'\n'));}
 save('validated-before-model-release');
 var fresh=null,changed=false;
 try{
  Fs.write(new F(out,'ledger-before.json').toPath(),Fs.readAllBytes(new F(ledgerPath).toPath()));
  var CT=Java.type('org.openpnp.machine.reference.driver.GcodeDriver$CommandType');
  if(String(d.getCommand(top,CT.MOVE_TO_COMPLETE_COMMAND)).trim()!=='M400 ; Wait for moves to complete before returning'||Number(d.getTimeoutMilliseconds())!==10000)throw Error('Reviewed fixed M400 completion changed');
  eval(String(new java.lang.String(Fs.readAllBytes(new F(root+'automation/paste/connection-policy.cjs').toPath()),UTF)));
  var prior=[];for each(var line in d.receiveResponses())prior.push(String(line.getLine()));PasteConnectionPolicy.responses(prior);if(prior.length)throw Error('Unexpected response before fresh M400');
  r.completionOnlySubmitted=true;save('sending-fixed-M400-no-motion');d.waitForCompletion(top,Java.type('org.openpnp.spi.MotionPlanner$CompletionType').WaitForStillstand);
  var lines=[];for each(var line in d.receiveResponses())lines.push(String(line.getLine()));r.completionResponses=lines;PasteConnectionPolicy.responses(lines);if(!lines.some(function(line){return /^ok/.test(line);}))throw Error('Fresh M400 ACK missing');
  if(d.isMotionPending())throw Error('Native pending flag not cleared');expectedPending=false;gate();r.nativePendingCleared=true;
  if(hash(Fs.readAllBytes(new F(ledgerPath).toPath()))!==ledgerHash)throw Error('Fault ledger changed during completion');
  ledger.status='verified';ledger.lastVerifiedB=280;last.status='verified';last.reconciliationEvidence={path:root+'automation/evidence/paste-prime-stop-audit-'+id+'/report.json',sha256:auditHash};last.originalFaultEvidence={path:root+'automation/evidence/paste-waste-prime-'+id+'/report.json',sha256:faultHash};
  var ledgerBytes=bytes(JSON.stringify(ledger,null,2)+'\n');Fs.write(new F(ledgerPath).toPath(),ledgerBytes);r.completedLedgerSha256=hash(ledgerBytes);if(hash(Fs.readAllBytes(new F(ledgerPath).toPath()))!==r.completedLedgerSha256)throw Error('Reconciled ledger write not verified');
  // Exact constructor from installed AbstractMachine.submit bytecode. Constructing
  // this executor starts no worker; no task is submitted by this script.
  fresh=new (Java.type('java.util.concurrent.ThreadPoolExecutor'))(1,1,1,Java.type('java.util.concurrent.TimeUnit').SECONDS,new (Java.type('java.util.concurrent.LinkedBlockingQueue'))());
  if(fresh.getPoolSize()!==0||fresh.getActiveCount()!==0||!fresh.getQueue().isEmpty())throw Error('Replacement executor unexpectedly active');
  gate();exField.set(m,fresh);changed=true;ownerField.set(m,null);m.fireMachineBusy(false);
  if(m.isBusy()||exField.get(m)!==fresh||ownerField.get(m)!==null||fresh.isShutdown()||fresh.getPoolSize()!==0||!fresh.getQueue().isEmpty())throw Error('Release postcheck failed');
  same(snapshot());if(configHash()!==audit.liveConfigurationSha256)throw Error('Configuration changed during release');
  r.after=snapshot();r.replacementPoolSize=fresh.getPoolSize();r.latchCleared=true;r.finishedAt=new Date().toISOString();save('model-release-complete-no-motion-no-replay');
  var terminal={schema:1,id:id,status:'completed-waste-prime-awaiting-observation',request:fault.request,finishedAt:new Date().toISOString(),afterQuerySnapshot:audit.afterQuerySnapshot,after:{reported:audit.reported,counts:audit.counts},controllerPositionVerified:true,countsVerified:true,uncertainCompletion:false,reservedCumulativeDegrees:440,completedLedgerSha256:r.completedLedgerSha256,reconciledAfterTimeout:true,originalFaultEvidence:last.originalFaultEvidence,auditEvidence:last.reconciliationEvidence,releaseReportPath:String(new F(out,'report.json')),physicalAcceptanceEstablished:false,calibrationEstablished:false};Fs.write(new F(out,'reconciled-terminal.json').toPath(),bytes(JSON.stringify(terminal,null,2)+'\n'));
 }catch(e){
  r.error=String(e);if(changed){ownerField.set(m,oldOwner);exField.set(m,oldEx);try{m.fireMachineBusy(true);}catch(notifyError){r.notificationError=String(notifyError);}}if(fresh!==null)fresh.shutdown();r.latchCleared=false;r.finishedAt=new Date().toISOString();save('release-failed-old-latch-restored');throw e;
 }
 print(String(out));
})();
