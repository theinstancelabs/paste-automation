// Exact ledger-only reconciliation of one audited, cooperatively stopped partial batch.
// No controller query, motion, cache setter, task, config save or replay.
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
 if(audit.faultId!==id||audit.faultSha256!==faultHash||audit.status!=='audit-complete-awaiting-separate-reviewed-latch-clear'||audit.positionVerified!==true||audit.stationaryImagesCaptured!==true||audit.latchCleared!==false||audit.motionIssued!==false||audit.verifiedPartialStop!==true||audit.completedStageCount!==52||audit.lastVerifiedStageIndex!==51||audit.lastVerifiedB!==-3174||fault.status!=='stopped-contiguous-batch-no-retry'||fault.stages.length!==52||fault.stages[51].targetRaw.B!==-3174||fault.reservedAbsoluteDegrees!==8967||fault.uncertainCompletion!==false||fault.transportUncertain!==false||fault.controllerPositionVerified!==true||fault.executorQuarantined!==true||fault.queuedTasksCancelled!==0)throw Error('Not the reviewed completed partial-batch audit');
 var zObs=verified(root+'automation/evidence/paste-z-observation-c16f85cc-bd6b-4877-9e93-b0a7274ec402/report.json','9820b56fdd3912c81fba9c9522fb49616d324976bb74022e644f4d68aeedbf44'),barrier=verified(root+'automation/evidence/paste-position-barrier-d843a2b4-d543-4f3d-8bb0-2027c6db0957/report.json','53bc8d5cbd61f55e80fb974d754f4b9f50e41942cfaa4f8b5e5de01b525ae334');
 var release=verified(root+'automation/evidence/paste-batch-stop-release-'+id+'/report.json','278de201fe6f2732bb975ec6c23ff7ce2e9b397fb69193b0072c12861db9b924');
 if(release.status!=='model-release-complete-no-motion-no-replay'||release.ledgerModified!==false||zObs.status!=='completed-Z-observation-awaiting-image-review'||zObs.controllerPositionVerified!==true||zObs.uncertainCompletion!==false||zObs.request.axis!=='Z'||zObs.request.deltaMm!==-5||zObs.request.expectedRaw.B!==-3174||zObs.after.reported.B!==-3174||zObs.after.reported.Z!==53.25||zObs.afterQuerySnapshot.raw.Z!==53.25||barrier.status!=='completed-read-only-position-barrier'||barrier.afterQuerySnapshot.raw.Z!==58.25||barrier.afterQuerySnapshot.raw.B!==-3174||zObs.request.barrierEvidence.path!==root+'automation/evidence/paste-position-barrier-d843a2b4-d543-4f3d-8bb0-2027c6db0957/report.json'||zObs.request.barrierEvidence.sha256!=='53bc8d5cbd61f55e80fb974d754f4b9f50e41942cfaa4f8b5e5de01b525ae334'||JSON.stringify(zObs.beforeQuerySnapshot.raw)!==JSON.stringify(barrier.afterQuerySnapshot.raw)||release.before.raw.Z!==58.25||release.before.raw.B!==-3174)throw Error('Reviewed release and post-lift observation/barrier required');
 var age=Number(Java.type('java.lang.System').currentTimeMillis())-Date.parse(zObs.finishedAt);if(age<0||age>600000)throw Error('Post-lift observation expired');
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
 function same(s){if(Object.keys(s.raw).sort().join(',')!=='A,B,X,Y,Z')throw Error('Raw axes changed');['raw','driver'].forEach(function(kind){['X','Y','Z','A','B'].forEach(function(k){close(s[kind][k],zObs.afterQuerySnapshot[kind][k],kind+' '+k);});});['N1','N2','top','bottom'].forEach(function(k){['x','y','z','rotation'].forEach(function(a){close(s.nativePoses[k][a],zObs.afterQuerySnapshot.nativePoses[k][a],k+' '+a);});});}
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
 var rid='c8113b57-6a31-4db9-8ccf-45c4d1138c66',out=new F(root+'automation/evidence/paste-batch-reconciliation-'+rid);
 if(!out.mkdir())throw Error('Reconciliation already claimed; no retry');
 var beforeBytes=Fs.readAllBytes(new F(fault.ledgerPath).toPath()),old=JSON.parse(String(new java.lang.String(beforeBytes,UTF)));
 load(root+'automation/paste/commissioning-stroke.cjs');var next=CommissioningStroke.reconcileStoppedPartialBatch(old,audit);
 if(JSON.stringify(next.entries.slice(0,-1))!==JSON.stringify(old.entries)||next.totalAbsoluteDegrees!==8967||next.lastVerifiedB!==-3174)throw Error('Fault history or charge changed');
 var r={schema:1,id:rid,request:{id:rid,sessionId:old.sessionId,jvmStartMs:jvm,liveConfigurationSha256:audit.liveConfigurationSha256},scope:'exact-audited-partial-batch-ledger-reconciliation',startedAt:new Date().toISOString(),faultId:id,faultSha256:faultHash,auditSha256:auditHash,releaseSha256:'278de201fe6f2732bb975ec6c23ff7ce2e9b397fb69193b0072c12861db9b924',postLiftObservationSha256:'9820b56fdd3912c81fba9c9522fb49616d324976bb74022e644f4d68aeedbf44',postLiftBarrierSha256:'53bc8d5cbd61f55e80fb974d754f4b9f50e41942cfaa4f8b5e5de01b525ae334',faultedLedgerSha256:audit.ledgerSha256,ledgerPath:fault.ledgerPath,verifiedPartialStop:true,executedBStages:20,executedGrossDegrees:160,unexecutedGrossDegrees:79,lastVerifiedB:-3174,reservedGrossDegrees:239,cumulativeGrossDegrees:8967,motionIssued:false,queryIssued:false,replayIssued:false,uncertainCompletion:false,ledgerModified:false,before:snapshot()};
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
  CommissioningStroke.validatePreviousReport(Object.assign?Object.assign({},r,{status:'completed-partial-batch-ledger-reconciliation-no-motion'}):(function(){var x=JSON.parse(JSON.stringify(r));x.status='completed-partial-batch-ledger-reconciliation-no-motion';return x;})(),next,nextHash,Date.parse(r.finishedAt));
  save('completed-partial-batch-ledger-reconciliation-no-motion');
 }catch(e){r.error=String(e);r.finishedAt=new Date().toISOString();save('reconciliation-failed-no-retry-no-refund');throw e;}
 print(String(out));
})();
