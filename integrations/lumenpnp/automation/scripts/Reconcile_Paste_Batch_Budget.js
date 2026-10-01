// Exact ledger-only reconciliation of one audited, unexecuted pre-dose fault.
// No controller query, motion, cache setter, task, config save or replay.
(function(){
 var C=Java.type('org.openpnp.model.Configuration'),F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8,
 MD=Java.type('java.security.MessageDigest'),AL=Java.type('org.openpnp.model.AxesLocation'),MM=Java.type('org.openpnp.model.LengthUnit').Millimeters;
 var root='/home/lumen/lumenpnp/',id='b67374aa-8c39-413d-abca-a2eee9f92768',faultHash='9728056a1a3e8598e03ed75e35c1053d57af5b11d5e7cc377fc74f555361358c',auditHash='74506ab2f3f7163c35664478b0f394d80bda3e27da1aabef44aec984f96e409f';
 function bytes(s){return new java.lang.String(s).getBytes(UTF);}
 function hash(b){var a=MD.getInstance('SHA-256').digest(b),s='';for(var i=0;i<a.length;i++)s+=('0'+((a[i]&255).toString(16))).slice(-2);return s;}
 function verified(path,expected){var b=Fs.readAllBytes(new F(path).toPath());if(hash(b)!==expected)throw Error('Reviewed artifact changed: '+path);return JSON.parse(String(new java.lang.String(b,UTF)));}
 function field(c,n){var f=Java.type(c).class.getDeclaredField(n);f.setAccessible(true);return f;}
 function close(a,b,label){if(typeof a!=='number'||typeof b!=='number'||!isFinite(a)||!isFinite(b)||Math.abs(a-b)>0.0001)throw Error(label+' changed');}
 var fault=verified(root+'automation/evidence/paste-contiguous-batch-'+id+'/report.json',faultHash),audit=verified(root+'automation/evidence/paste-batch-stop-audit-'+id+'/report.json',auditHash);
 if(audit.faultId!==id||audit.faultSha256!==faultHash||audit.status!=='audit-complete-awaiting-separate-reviewed-latch-clear'||audit.positionVerified!==true||audit.stationaryImagesCaptured!==true||audit.latchCleared!==false||audit.motionIssued!==false||audit.confirmedNoBStageSubmitted!==true||audit.verifiedNoBCountChange!==true||audit.completedZStepCounts!==200||fault.stages.length!==3||fault.stages.some(function(s){return s.axis==='B';})||fault.stages[2].nativeMotionCompletionReported!==true||fault.error!=='Error: cycle target Y mismatch')throw Error('Not the reviewed completed audit');
 var norm=verified(root+'automation/evidence/paste-survey-e6c1cd66-98c0-4bc9-be5e-e5a786243b4f/report.json','6c4f7440c0f4a5fdfd621ce0e6e7f3392df5ad0df01dc3f1f322fd23cc37f945');
 var release=verified(root+'automation/evidence/paste-batch-stop-release-'+id+'/report.json','0d1b6ebdbab5c121be53faf9a9370c8693d3f9fa437f23a61ae8a069824f485c');
 if(release.status!=='model-release-complete-no-motion-no-replay'||release.ledgerModified!==false||norm.status!=='completed-camera-survey-awaiting-image-review'||norm.controllerPositionVerified!==true||norm.independentFirmwareStepVerified!==true||norm.uncertainCompletion!==false||norm.commandedControllerAxes.join(',')!=='Y'||norm.after.reported.B!==-1130||norm.after.responses.indexOf('X:288.93 Y:219.88 Z:53.25 A:720.00 B:-1130.00 Count X:92458 Y:70362 Z:2130 A:3197 B:-5017')<0)throw Error('Reviewed normalization/release required');
 var age=Number(java.lang.System.currentTimeMillis())-Date.parse(norm.finishedAt);if(age<0||age>600000)throw Error('Normalization evidence expired');
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
 function same(s){if(Object.keys(s.raw).sort().join(',')!=='A,B,X,Y,Z')throw Error('Raw axes changed');['raw','driver'].forEach(function(kind){['X','Y','Z','A','B'].forEach(function(k){close(s[kind][k],norm.afterQuerySnapshot[kind][k],kind+' '+k);});});['N1','N2','top','bottom'].forEach(function(k){['x','y','z','rotation'].forEach(function(a){close(s.nativePoses[k][a],norm.afterQuerySnapshot.nativePoses[k][a],k+' '+a);});});}
 function gate(){
  if(m.isBusy()||!m.isEnabled()||!m.isHomed()||String(state.get(panel))!=='Stopped')throw Error('Latched machine state changed');
  if(oldEx==null||oldEx.isShutdown()||oldEx.isTerminated()||oldEx.getActiveCount()!==0||!oldEx.getQueue().isEmpty()||exField.get(m)!==oldEx||ownerField.get(m)!==oldOwner)throw Error('Expected unchanged idle native executor');
  if(String(field('org.openpnp.machine.reference.driver.GcodeDriver','connected').get(d))!=='true'||d.isMotionPending()||field('org.openpnp.machine.reference.driver.AbstractMotionPlanner','motionCommands').get(planner).size()!==0)throw Error('Driver changed or motion pending');
  if(right.getNozzleTip()!=null||right.getCompatibleNozzleTips().size()!==0||right.getRotationModeOffset()!=null||right.isChangerEnabled()||m.getPnpJobProcessor().isPreRotateAllNozzles())throw Error('Quarantine changed');
  var reader=field('org.openpnp.machine.reference.driver.GcodeDriver','readerThread').get(d);if(reader==null||!reader.isAlive()||field('org.openpnp.machine.reference.driver.GcodeDriver','errorResponse').get(d)!=null||d.isInSimulationMode())throw Error('Reader fault/simulation');
  if(hash(Fs.readAllBytes(new F(fault.ledgerPath).toPath()))!==audit.ledgerSha256)throw Error('Faulted ledger changed');
  if(configHash()!==audit.liveConfigurationSha256)throw Error('Live configuration changed');same(snapshot());
 }
 gate();
 var rid='a6b138b6-2c91-4198-a057-684c3ab39dae',out=new F(root+'automation/evidence/paste-batch-reconciliation-'+rid);
 if(!out.mkdir())throw Error('Reconciliation already claimed; no retry');
 var beforeBytes=Fs.readAllBytes(new F(fault.ledgerPath).toPath()),old=JSON.parse(String(new java.lang.String(beforeBytes,UTF)));
 load(root+'automation/paste/commissioning-stroke.cjs');var next=CommissioningStroke.reconcileUnexecutedBatch(old,audit);
 if(JSON.stringify(next.entries.slice(0,-1))!==JSON.stringify(old.entries)||next.totalAbsoluteDegrees!==1782||next.lastVerifiedB!==-1130)throw Error('Fault history or charge changed');
 var r={schema:1,id:rid,request:{id:rid,sessionId:old.sessionId,jvmStartMs:jvm,liveConfigurationSha256:audit.liveConfigurationSha256},scope:'exact-pre-dose-batch-ledger-reconciliation',startedAt:new Date().toISOString(),faultId:id,faultSha256:faultHash,auditSha256:auditHash,normalizationSha256:'6c4f7440c0f4a5fdfd621ce0e6e7f3392df5ad0df01dc3f1f322fd23cc37f945',faultedLedgerSha256:audit.ledgerSha256,ledgerPath:fault.ledgerPath,confirmedNoBStageSubmitted:true,executedBStages:0,chargedUnexecutedDegrees:40,lastVerifiedB:-1130,reservedGrossDegrees:1782,motionIssued:false,queryIssued:false,replayIssued:false,uncertainCompletion:false,ledgerModified:false,before:snapshot()};
 function save(status){r.status=status;Fs.write(new F(out,'report.json').toPath(),bytes(JSON.stringify(r,null,2)+'\n'));}
 save('validated-before-ledger-reconciliation');
 try{
  Fs.write(new F(out,'faulted-ledger-preserved.json').toPath(),beforeBytes);
  var nextBytes=bytes(JSON.stringify(next,null,2)+'\n'),nextHash=hash(nextBytes),staged=new F(out,'reconciled-ledger.json');Fs.write(staged.toPath(),nextBytes);
  gate();if(hash(Fs.readAllBytes(new F(fault.ledgerPath).toPath()))!==audit.ledgerSha256)throw Error('Ledger changed before reconciliation');
  Fs.move(staged.toPath(),new F(fault.ledgerPath).toPath(),Java.type('java.nio.file.StandardCopyOption').ATOMIC_MOVE,Java.type('java.nio.file.StandardCopyOption').REPLACE_EXISTING);
  r.ledgerModified=true;if(hash(Fs.readAllBytes(new F(fault.ledgerPath).toPath()))!==nextHash)throw Error('Reconciled ledger hash differs');
  same(snapshot());if(m.isBusy()||configHash()!==audit.liveConfigurationSha256)throw Error('State changed during reconciliation');
  r.completedLedgerSha256=nextHash;r.after=snapshot();r.finishedAt=new Date().toISOString();
  CommissioningStroke.validatePreviousReport(Object.assign?Object.assign({},r,{status:'completed-pre-dose-batch-reconciliation-no-motion'}):(function(){var x=JSON.parse(JSON.stringify(r));x.status='completed-pre-dose-batch-reconciliation-no-motion';return x;})(),next,nextHash,Date.parse(r.finishedAt));
  save('completed-pre-dose-batch-reconciliation-no-motion');
 }catch(e){r.error=String(e);r.finishedAt=new Date().toISOString();save('reconciliation-failed-no-retry-no-refund');throw e;}
 print(String(out));
})();
