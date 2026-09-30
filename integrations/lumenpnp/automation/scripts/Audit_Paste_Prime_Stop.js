// READ-ONLY audit of one identified B-prime M400 timeout. Retains pending flag and latch. No motion, completion,
// task submission, serial connection, config save, enable/home or latch clearing.
(function(){
 var C=Java.type('org.openpnp.model.Configuration'),F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8,
 MD=Java.type('java.security.MessageDigest'),AL=Java.type('org.openpnp.model.AxesLocation'),MM=Java.type('org.openpnp.model.LengthUnit').Millimeters,
 CT=Java.type('org.openpnp.machine.reference.driver.GcodeDriver$CommandType'),I=Java.type('javax.imageio.ImageIO');
 var root='/home/lumen/lumenpnp/',id='ba7bf3db-7458-47e4-9e80-d9f90df6ac89',faultFile=new F(root+'automation/evidence/paste-waste-prime-'+id+'/report.json'),faultHash='e68ca2c1f912d41bbabb06a8664941e90f480f354d6f3063fe99b56bbed79032';
 function bytes(s){return new java.lang.String(s).getBytes(UTF);}
 function hash(b){var a=MD.getInstance('SHA-256').digest(b),s='';for(var i=0;i<a.length;i++)s+=('0'+((a[i]&255).toString(16))).slice(-2);return s;}
 function read(f){return String(new java.lang.String(Fs.readAllBytes(f.toPath()),UTF));}
 function field(c,n,o){var f=Java.type(c).class.getDeclaredField(n);f.setAccessible(true);return f.get(o);}
 function close(a,b,t,label){if(typeof a!=='number'||typeof b!=='number'||!isFinite(a)||!isFinite(b)||Math.abs(a-b)>t)throw Error(label+' mismatch');}
 function five(a,b,t,label){if(Object.keys(a).sort().join(',')!=='A,B,X,Y,Z'||Object.keys(b).sort().join(',')!=='A,B,X,Y,Z')throw Error('Incomplete axes');['X','Y','Z','A','B'].forEach(function(k){close(a[k],b[k],t===null?(k==='A'||k==='B'?0.3:0.02):t,label+' '+k);});}
 if(hash(Fs.readAllBytes(faultFile.toPath()))!==faultHash)throw Error('Exact reviewed fault artifact changed');
 var f=JSON.parse(read(faultFile));
 if(f.id!==id||f.status!=='failed-no-retry-no-recovery-motion'||!/^java.lang.Exception: GcodeDriver:.* timeout waiting for response to M400 ; Wait for moves to complete before returning$/.test(f.error)||f.uncertainCompletion!==true||f.motionSubmitted!==true||f.executorQuarantined!==true||f.queuedTasksCancelled!==0||f.after||f.controllerPositionVerified)throw Error('Not the reviewed rounding stop');
 if(!isFinite(Date.parse(f.finishedAt))||Number(java.lang.System.currentTimeMillis())-Date.parse(f.finishedAt)<60000)throw Error('Wait for60seconds after fault before read-only reconciliation');
 var m=C.get().getMachine(),planner=m.getMotionPlanner(),jvm=Number(Java.type('java.lang.management.ManagementFactory').getRuntimeMXBean().getStartTime());
 if(jvm!==f.request.jvmStartMs||m.getDrivers().size()!==1)throw Error('Session/topology changed');
 var d=m.getDrivers().get(0),ex=field('org.openpnp.spi.base.AbstractMachine','executor',m),owner=field('org.openpnp.spi.base.AbstractMachine','taskThread',m);
 if(String(d.getClass().getName())!=='org.openpnp.machine.reference.driver.GcodeDriver'||String(d.getId())!=='DRV16982438146c1dd4'||String(planner.getClass().getName())!=='org.openpnp.machine.reference.driver.NullMotionPlanner')throw Error('Unknown native owner');
 var jar=new F(d.getClass().getProtectionDomain().getCodeSource().getLocation().toURI());if(hash(Fs.readAllBytes(jar.toPath()))!=='bcd34923ae91d61a96b98b4c82c93cdc90093ff94292270fd0a18fc6f96f7752')throw Error('Native API changed');
 var head=m.getDefaultHead(),left=head.getNozzleByName('N1'),right=head.getNozzleByName('N2'),top=head.getDefaultCamera(),bottom=null;
 for each(var camera in m.getCameras())if(String(camera.getLooking())==='Up'){if(bottom!==null)throw Error('Ambiguous bottom camera');bottom=camera;}
 if(left==null||right==null||top==null||bottom==null||String(top.getId())!=='CAM1607555396816'||String(right.getId())!=='NOZ1710829fd33a0170')throw Error('Head/camera changed');
 var panel=Java.type('org.openpnp.gui.MainFrame').get().getJobTab(),state=panel.getClass().getDeclaredField('state');state.setAccessible(true);
 function configHash(){var w=new java.io.StringWriter();C.createSerializer().write(m,w);return hash(bytes(String(w)));}
 var reader=field('org.openpnp.machine.reference.driver.GcodeDriver','readerThread',d);
 function gate(){
  if(reader==null||!reader.isAlive()||field('org.openpnp.machine.reference.driver.GcodeDriver','readerThread',d)!==reader||field('org.openpnp.machine.reference.driver.GcodeDriver','errorResponse',d)!=null)throw Error('Native reader failed or error response latched');
  if(!m.isBusy()||!m.isEnabled()||!m.isHomed()||String(state.get(panel))!=='Stopped')throw Error('Expected stopped enabled/homed latched machine');
  if(ex==null||!ex.isShutdown()||!ex.isTerminated()||ex.getActiveCount()!==0||!ex.getQueue().isEmpty()||owner==null||owner.isAlive())throw Error('Executor not terminated or retained owner still alive');
  if(field('org.openpnp.spi.base.AbstractMachine','executor',m)!==ex||field('org.openpnp.spi.base.AbstractMachine','taskThread',m)!==owner)throw Error('Native executor/owner changed');
  if(String(field('org.openpnp.machine.reference.driver.GcodeDriver','connected',d))!=='true'||!d.isMotionPending()||field('org.openpnp.machine.reference.driver.AbstractMotionPlanner','motionCommands',planner).size()!==0)throw Error('Connection changed or motion pending');
  if(right.getNozzleTip()!=null||right.getCompatibleNozzleTips().size()!==0||right.getRotationModeOffset()!=null||right.isChangerEnabled()||m.getPnpJobProcessor().isPreRotateAllNozzles())throw Error('Quarantine changed');
  for each(var h in m.getHeads())for each(var n in h.getNozzles())if(n.getPart()!=null||n.getPartsFeeder()!=null)throw Error('Held/associated part');
  if(['M114','M114 ; get position'].indexOf(String(d.getCommand(null,CT.GET_POSITION_COMMAND)).trim())<0)throw Error('Query command changed');
  if(configHash()!==f.request.liveConfigurationSha256)throw Error('Live configuration changed');
 }
 var axes={},ids={X:'AXS169824381580efcb',Y:'AXS16982438158c4660',Z:'AXS16982438158d0458',A:'AXS16b068df4e35374e',B:'AXS17108288e61da5fb'};
 for each(var a in new AL(m).drivenBy(d).getControllerAxes()){var k=String(a.getLetter());if(!ids[k]||String(a.getId())!==ids[k]||axes[k])throw Error('Unexpected axis');axes[k]=a;}
 function snapshot(){var s={raw:{},driver:{},nativePoses:{}};Object.keys(axes).forEach(function(k){s.raw[k]=Number(axes[k].getCoordinate());s.driver[k]=Number(axes[k].getDriverCoordinate());});var all={N1:left,N2:right,top:top,bottom:bottom};Object.keys(all).forEach(function(k){var p=all[k].getLocation().convertToUnits(MM);s.nativePoses[k]={x:Number(p.getX()),y:Number(p.getY()),z:Number(p.getZ()),rotation:Number(p.getRotation())};});return s;}
 gate();var before=snapshot();five(before.raw,f.expectedAfterRaw,0.0001,'unchanged fault model');five(before.driver,f.expectedAfterRaw,0.0001,'unchanged fault driver');five(before.raw,f.expectedAfterRaw,null,'target model');
 var out=new F(root+'automation/evidence/paste-prime-stop-audit-'+id);if(!out.mkdir())throw Error('Audit already claimed; review existing artifact');
 var r={schema:1,scope:'read-only-specific-prime-timeout-audit',faultId:id,faultPath:String(faultFile),faultSha256:faultHash,jvmStartMs:jvm,startedAt:new Date().toISOString(),liveConfigurationSha256:configHash(),beforeQuerySnapshot:before,expectedAfterRaw:f.expectedAfterRaw,positionVerified:false,stationaryImagesCaptured:false,latchCleared:false,motionIssued:false,physicalAcceptanceEstablished:false,calibrationEstablished:false};
 function save(status){r.status=status;Fs.write(new F(out,'report.json').toPath(),bytes(JSON.stringify(r,null,2)+'\n'));}
 function capture(c,name){if(String(c.getClass().getName())!=='org.openpnp.machine.reference.camera.OpenPnpCaptureCamera')throw Error('Unknown capture class');var open=c.getClass().getDeclaredMethod('isOpen');open.setAccessible(true);if(!open.invoke(c))throw Error('Camera closed; no reopen');var img=c.captureRaw(),dest=new F(out,name+'.png');if(img==null||!I.write(img,'png',dest))throw Error('Capture failed');return {path:String(dest),sha256:hash(Fs.readAllBytes(dest.toPath())),width:img.getWidth(),height:img.getHeight()};}
 save('saved-model-before-M114');
 try{
  eval(read(new F(root+'automation/paste/connection-policy.cjs')));eval(read(new F(root+'automation/paste/waste-prime.cjs')));
  var prior=[];for each(var line in d.receiveResponses())prior.push(String(line.getLine()));r.priorResponses=prior;PasteConnectionPolicy.responses(prior);if(prior.some(function(line){return /[XYZAB]:/.test(line);}))throw Error('Stale position before query');
  if(!prior.some(function(line){return /^ok/.test(line);}))throw Error('No late completion ACK available; latch retained');r.lateCompletionAckObserved=true;save('late-ACK-observed-before-M114');
  var observed=d.getReportedLocation(3000),reported={},lines=[];for each(var a in observed.getControllerAxes())reported[String(a.getLetter())]=Number(observed.getCoordinate(a));
  function append(list){for each(var line in list)lines.push(String(line.getLine()));}
  var timeout=new (Java.type('org.openpnp.machine.reference.driver.GcodeDriver$TimeoutAction'))({apply:function(partial){append(partial);r.responses=lines;save('M114-response-timeout');throw new java.lang.Exception('Fresh audit query timed out; latch retained');}});
  var positionRegex=String(d.getCommand(null,CT.POSITION_REPORT_REGEX));append(d.receiveResponses(positionRegex,3000,timeout));
  var delimiter=-1;lines.forEach(function(line,i){if(/^X:/.test(line))delimiter=i;});if(delimiter<0)throw Error('No fresh full position delimiter');
  if(!lines.slice(delimiter+1).some(function(line){return /^ok/.test(line);}))append(d.receiveResponses('^ok.*',3000,timeout));append(d.receiveResponses());
  r.reported=reported;r.responses=lines;save('M114-observed');PasteConnectionPolicy.responses(lines);
  r.counts=PasteWastePrime.fullResponse(lines,reported,f.expectedAfterRaw);PasteWastePrime.countsStep(f.before.counts,r.counts,f.request);r.countsVerified=true;
  five(reported,before.raw,null,'reported/saved model');five(reported,before.driver,null,'reported/saved driver');five(reported,f.expectedAfterRaw,null,'reported intended target');
  ['X','Y','Z','A'].forEach(function(k){close(reported[k],f.beforeQuerySnapshot.raw[k],k==='A'?0.3:0.02,'unchanged nonB '+k);});
  var after=snapshot();r.afterQuerySnapshot=after;five(after.raw,before.raw,0.0001,'unchanged query model');five(after.driver,reported,null,'query driver');r.positionVerified=true;save('position-verified-latch-retained');
  gate();r.images={top:capture(top,'top-stationary-raw'),bottom:capture(bottom,'bottom-stationary-raw')};r.stationaryImagesCaptured=true;gate();
  r.finishedAt=new Date().toISOString();save('audit-complete-awaiting-separate-reviewed-latch-clear');
 }catch(e){r.error=String(e);r.finishedAt=new Date().toISOString();save('audit-failed-latch-retained-no-motion');throw e;}
 print(String(out));
})();
