// STAGED READ-ONLY audit of one identified pre-dose batch stop. No motion, completion,
// task submission, serial connection, config save, enable/home or latch clearing.
(function(){
 var C=Java.type('org.openpnp.model.Configuration'),F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8,
 MD=Java.type('java.security.MessageDigest'),AL=Java.type('org.openpnp.model.AxesLocation'),MM=Java.type('org.openpnp.model.LengthUnit').Millimeters,
 CT=Java.type('org.openpnp.machine.reference.driver.GcodeDriver$CommandType'),I=Java.type('javax.imageio.ImageIO');
 var root='/home/lumen/lumenpnp/',id='b67374aa-8c39-413d-abca-a2eee9f92768',faultFile=new F(root+'automation/evidence/paste-contiguous-batch-'+id+'/report.json'),faultHash='9728056a1a3e8598e03ed75e35c1053d57af5b11d5e7cc377fc74f555361358c';
 function bytes(s){return new java.lang.String(s).getBytes(UTF);}
 function hash(b){var a=MD.getInstance('SHA-256').digest(b),s='';for(var i=0;i<a.length;i++)s+=('0'+((a[i]&255).toString(16))).slice(-2);return s;}
 function read(f){return String(new java.lang.String(Fs.readAllBytes(f.toPath()),UTF));}
 function field(c,n,o){var f=Java.type(c).class.getDeclaredField(n);f.setAccessible(true);return f.get(o);}
 function close(a,b,t,label){if(typeof a!=='number'||typeof b!=='number'||!isFinite(a)||!isFinite(b)||Math.abs(a-b)>t)throw Error(label+' mismatch');}
 function five(a,b,t,label){if(Object.keys(a).sort().join(',')!=='A,B,X,Y,Z'||Object.keys(b).sort().join(',')!=='A,B,X,Y,Z')throw Error('Incomplete axes');['X','Y','Z','A','B'].forEach(function(k){close(a[k],b[k],t===null?(k==='A'||k==='B'?0.3:0.02):t,label+' '+k);});}
 if(hash(Fs.readAllBytes(faultFile.toPath()))!==faultHash)throw Error('Exact reviewed fault artifact changed');
 var f=JSON.parse(read(faultFile));
 if(f.id!==id||f.status!=='failed-no-retry-no-recovery-motion'||f.error!=='Error: cycle target Y mismatch'||f.motionSubmitted!==true||f.executorQuarantined!==true||f.queuedTasksCancelled!==0||f.controllerPositionVerified!==false||f.stages.length!==3||f.stages.some(function(s){return s.axis==='B';})||!f.stages[0].verified||!f.stages[1].verified||f.stages[2].axis!=='Z'||f.stages[2].verified!==false||f.stages[2].nativeMotionCompletionReported!==true||f.stage2)throw Error('Not the exact reviewed pre-dose rounding stop');
 var diagnosticFile=new F(root+'.local-machine-backups/paste-live-model-state-1790837538678/report.json'),diagnosticHash='3e1f2c8527a00119b7619c963b9cb5c5f23bf1e848c2f1b2637cc816e8f2e2de',ledgerFile=new F(f.ledgerPath),ledgerHash='cd47fafbe31512a904fc43420b84033fc8abd36d0fc1eb2131a19e13dd2ce2a8';
 if(hash(Fs.readAllBytes(diagnosticFile.toPath()))!==diagnosticHash||hash(Fs.readAllBytes(ledgerFile.toPath()))!==ledgerHash)throw Error('Exact diagnostic/ledger changed');
 var diagnostic=JSON.parse(read(diagnosticFile)),ledger=JSON.parse(read(ledgerFile));if(ledger.status!=='faulted'||ledger.totalAbsoluteDegrees!==1782||ledger.lastVerifiedB!==-1130||ledger.entries.slice(-2).some(function(e){return e.status!=='faulted'||e.batchId!==id;}))throw Error('Faulted reserved budget must remain untouched');
 var expectedTarget=f.stages[2].targetRaw,expectedCounts={X:92458,Y:70360,Z:2330,A:3197,B:-5017};

 var m=C.get().getMachine(),planner=m.getMotionPlanner(),jvm=Number(Java.type('java.lang.management.ManagementFactory').getRuntimeMXBean().getStartTime());
 if(jvm!==diagnostic.jvmStartMs||jvm!==f.request.jvmStartMs||m.getDrivers().size()!==1)throw Error('Session/topology changed');
 var d=m.getDrivers().get(0),ex=field('org.openpnp.spi.base.AbstractMachine','executor',m),owner=field('org.openpnp.spi.base.AbstractMachine','taskThread',m);
 if(String(d.getClass().getName())!=='org.openpnp.machine.reference.driver.GcodeDriver'||String(d.getId())!=='DRV16982438146c1dd4'||String(planner.getClass().getName())!=='org.openpnp.machine.reference.driver.NullMotionPlanner')throw Error('Unknown native owner');
 var jar=new F(d.getClass().getProtectionDomain().getCodeSource().getLocation().toURI());if(hash(Fs.readAllBytes(jar.toPath()))!=='bcd34923ae91d61a96b98b4c82c93cdc90093ff94292270fd0a18fc6f96f7752')throw Error('Native API changed');
 var head=m.getDefaultHead(),left=head.getNozzleByName('N1'),right=head.getNozzleByName('N2'),top=head.getDefaultCamera(),bottom=null;
 for each(var camera in m.getCameras())if(String(camera.getLooking())==='Up'){if(bottom!==null)throw Error('Ambiguous bottom camera');bottom=camera;}
 if(left==null||right==null||top==null||bottom==null||String(top.getId())!=='CAM1607555396816'||String(right.getId())!=='NOZ1710829fd33a0170')throw Error('Head/camera changed');
 var panel=Java.type('org.openpnp.gui.MainFrame').get().getJobTab(),state=panel.getClass().getDeclaredField('state');state.setAccessible(true);
 function configHash(){var w=new java.io.StringWriter();C.createSerializer().write(m,w);return hash(bytes(String(w)));}
 function gate(){
  if(!m.isBusy()||!m.isEnabled()||!m.isHomed()||!planner.isHomed()||String(state.get(panel))!=='Stopped')throw Error('Expected stopped enabled/homed latched machine');
  if(ex==null||!ex.isShutdown()||!ex.isTerminated()||ex.getActiveCount()!==0||!ex.getQueue().isEmpty()||owner==null||owner.isAlive()||String(owner.getName())!==diagnostic.taskOwner.name)throw Error('Executor not terminated or retained owner still alive');
  if(field('org.openpnp.spi.base.AbstractMachine','executor',m)!==ex||field('org.openpnp.spi.base.AbstractMachine','taskThread',m)!==owner)throw Error('Native executor/owner changed');
  if(String(field('org.openpnp.machine.reference.driver.GcodeDriver','connected',d))!=='true'||d.isMotionPending()||field('org.openpnp.machine.reference.driver.AbstractMotionPlanner','motionCommands',planner).size()!==0)throw Error('Connection changed or motion pending');
  if(right.getNozzleTip()!=null||right.getCompatibleNozzleTips().size()!==0||right.getRotationModeOffset()!=null||right.isChangerEnabled()||m.getPnpJobProcessor().isPreRotateAllNozzles())throw Error('Quarantine changed');
  for each(var h in m.getHeads())for each(var n in h.getNozzles())if(n.getPart()!=null||n.getPartsFeeder()!=null)throw Error('Held/associated part');
  if(['M114','M114 ; get position'].indexOf(String(d.getCommand(null,CT.GET_POSITION_COMMAND)).trim())<0)throw Error('Query command changed');
  var reader=field('org.openpnp.machine.reference.driver.GcodeDriver','readerThread',d);if(reader==null||!reader.isAlive()||field('org.openpnp.machine.reference.driver.GcodeDriver','errorResponse',d)!=null||d.isInSimulationMode())throw Error('Native reader fault/simulation');
  var sub=field('org.openpnp.machine.reference.driver.AbstractMotionPlanner','subordinateMotion',planner),queue=field('org.openpnp.machine.reference.driver.AbstractMotionPlanner$SubordinateMotion','queue',sub);if(queue!=null&&!queue.isEmpty())throw Error('Subordinate motion queued');
  if(hash(Fs.readAllBytes(ledgerFile.toPath()))!==ledgerHash||hash(Fs.readAllBytes(faultFile.toPath()))!==faultHash)throw Error('Fault/ledger changed');
  if(configHash()!==f.request.liveConfigurationSha256)throw Error('Live configuration changed');
 }
 var axes={},ids={X:'AXS169824381580efcb',Y:'AXS16982438158c4660',Z:'AXS16982438158d0458',A:'AXS16b068df4e35374e',B:'AXS17108288e61da5fb'};
 for each(var a in new AL(m).drivenBy(d).getControllerAxes()){var k=String(a.getLetter());if(!ids[k]||String(a.getId())!==ids[k]||axes[k])throw Error('Unexpected axis');axes[k]=a;}
 function snapshot(){var s={raw:{},driver:{},nativePoses:{}};Object.keys(axes).forEach(function(k){s.raw[k]=Number(axes[k].getCoordinate());s.driver[k]=Number(axes[k].getDriverCoordinate());});var all={N1:left,N2:right,top:top,bottom:bottom};Object.keys(all).forEach(function(k){var p=all[k].getLocation().convertToUnits(MM);s.nativePoses[k]={x:Number(p.getX()),y:Number(p.getY()),z:Number(p.getZ()),rotation:Number(p.getRotation())};});return s;}
 gate();var before=snapshot();diagnostic.axes.forEach(function(a){close(before.raw[a.letter],a.raw,0.0001,'diagnostic model');close(before.driver[a.letter],a.driver,0.0001,'diagnostic driver');});five(before.raw,expectedTarget,null,'completed Z expected model');

 var out=new F(root+'automation/evidence/paste-batch-stop-audit-'+id);if(!out.mkdir())throw Error('Audit already claimed; review existing artifact');
 var r={schema:1,scope:'read-only-specific-pre-dose-batch-stop-audit',faultId:id,faultPath:String(faultFile),faultSha256:faultHash,jvmStartMs:jvm,startedAt:new Date().toISOString(),liveConfigurationSha256:configHash(),beforeQuerySnapshot:before,expectedAfterRaw:expectedTarget,expectedCounts:expectedCounts,diagnosticSha256:diagnosticHash,ledgerSha256:ledgerHash,reservedGrossDegrees:1782,positionVerified:false,stationaryImagesCaptured:false,latchCleared:false,motionIssued:false,physicalAcceptanceEstablished:false,calibrationEstablished:false};
 function save(status){r.status=status;Fs.write(new F(out,'report.json').toPath(),bytes(JSON.stringify(r,null,2)+'\n'));}
 function capture(c,name){if(String(c.getClass().getName())!=='org.openpnp.machine.reference.camera.OpenPnpCaptureCamera')throw Error('Unknown capture class');var open=c.getClass().getDeclaredMethod('isOpen');open.setAccessible(true);if(!open.invoke(c))throw Error('Camera closed; no reopen');var img=c.captureRaw(),dest=new F(out,name+'.png');if(img==null||!I.write(img,'png',dest))throw Error('Capture failed');return {path:String(dest),sha256:hash(Fs.readAllBytes(dest.toPath())),width:img.getWidth(),height:img.getHeight()};}
 save('saved-model-before-M114');
 try{
  eval(read(new F(root+'automation/paste/connection-policy.cjs')));eval(read(new F(root+'automation/paste/waste-prime.cjs')));
  var prior=[],lines=[];for each(var line in d.receiveResponses())prior.push(String(line.getLine()));r.priorResponses=prior;PasteConnectionPolicy.responses(prior);if(prior.some(function(l){return /\b[XYZAB]:/.test(l);}))throw Error('Unexpected stale position before fresh audit query');
  var regex='^.*X:(?<X>-?\\d+\\.\\d+)\\s*Y:(?<Y>-?\\d+\\.\\d+)\\s*Z:(?<Z>-?\\d+\\.\\d+)\\s*A:(?<A>-?\\d+\\.\\d+)\\s*B:(?<B>-?\\d+\\.\\d+).*';
  if(String(d.getCommand(null,CT.POSITION_REPORT_REGEX))!==regex||String(d.getCommand(null,CT.COMMAND_CONFIRM_REGEX)).trim()!=='^ok.*')throw Error('Position delimiter/ACK template changed');
  function append(rs){for each(var l in rs)lines.push(String(l.getLine()));}
  function collect(pattern){append(d.receiveResponses(pattern,3000,new (Java.type('org.openpnp.machine.reference.driver.GcodeDriver$TimeoutAction'))({apply:function(rs){append(rs);r.responses=lines;save('audit-response-timeout-latch-retained');throw new java.lang.Exception('Audit response timeout');}})));PasteConnectionPolicy.responses(lines);}
  r.controllerQuerySubmitted=true;save('fresh-M114-submitted');var observed=d.getReportedLocation(3000),reported={};for each(var a in observed.getControllerAxes())reported[String(a.getLetter())]=Number(observed.getCoordinate(a));collect(regex);
  var delimiter=-1;lines.forEach(function(l,index){if(/^X:/.test(l))delimiter=index;});if(delimiter<0)throw Error('Fresh audit position delimiter missing');if(!lines.slice(delimiter+1).some(function(l){return /^ok/.test(l);}))collect('^ok.*');append(d.receiveResponses());
  r.reported=reported;r.responses=lines;r.counts=PasteWastePrime.fullResponse(lines,reported,expectedTarget);Object.keys(expectedCounts).forEach(function(k){if(r.counts[k]!==expectedCounts[k])throw Error('Exact completed-Z/held-axis count mismatch '+k);});
  ['X','Y','A','B'].forEach(function(k){if(r.counts[k]!==f.stage1.counts[k])throw Error('Controller count moved on held axis '+k);});if(r.counts.Z-f.stage1.counts.Z!==200)throw Error('Completed Z must equal +200 controller steps');
  r.confirmedNoBStageSubmitted=true;r.verifiedNoBCountChange=true;r.completedZStepCounts=200;r.preciseCommandedTarget=expectedTarget;r.controllerPositionVerified=true;r.uncertainCompletion=false;save('fresh-position-counts-and-ACK-verified');
  var after=snapshot();r.afterQuerySnapshot=after;five(after.raw,before.raw,0.0001,'unchanged query model');five(after.driver,reported,null,'query driver');r.positionVerified=true;save('position-verified-latch-retained');
  gate();r.images={top:capture(top,'top-stationary-raw'),bottom:capture(bottom,'bottom-stationary-raw')};r.stationaryImagesCaptured=true;gate();
  r.finishedAt=new Date().toISOString();save('audit-complete-awaiting-separate-reviewed-latch-clear');
 }catch(e){r.error=String(e);r.finishedAt=new Date().toISOString();save('audit-failed-latch-retained-no-motion');throw e;}
 print(String(out));
})();
