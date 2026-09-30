// Reviewed bounded native N1 vacuum probe; fresh pose/evidence/baseline request required.
// Software activation is not physical contact calibration or permission to dispense.
var PASTE_VACUUM_PROBE_ENABLED = true;
if (!PASTE_VACUUM_PROBE_ENABLED) throw Error('Native vacuum probe disabled');
(function(){
 // No competing serial connection, actuator coordination API, nozzle moves,
 // generic task wrappers, pickup routines, or autonomous recovery/lift.
 var C=Java.type('org.openpnp.model.Configuration'),F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8,
 MD=Java.type('java.security.MessageDigest'),MM=Java.type('org.openpnp.model.LengthUnit').Millimeters,AL=Java.type('org.openpnp.model.AxesLocation'),MO=Java.type('org.openpnp.model.Motion$MotionOption'),CT=Java.type('org.openpnp.machine.reference.driver.GcodeDriver$CommandType'),I=Java.type('javax.imageio.ImageIO');
 var root='/home/lumen/lumenpnp/',m=C.get().getMachine(),planner=m.getMotionPlanner();
 function read(p){return String(new java.lang.String(Fs.readAllBytes(new F(p).toPath()),UTF));}
 function hash(b){var a=MD.getInstance('SHA-256').digest(b),s='';for(var i=0;i<a.length;i++)s+=('0'+((a[i]&255).toString(16))).slice(-2);return s;}
 function bytes(s){return new java.lang.String(s).getBytes(UTF);}
 function privateValue(c,n,o){var f=Java.type(c).class.getDeclaredField(n);f.setAccessible(true);return f.get(o);}
 function configHash(){var w=new java.io.StringWriter();C.createSerializer().write(m,w);return hash(bytes(String(w)));}
 eval(read(root+'automation/paste/vacuum-probe-native.cjs'));
 eval(read(root+'automation/paste/vacuum-probe-policy.cjs'));
 eval(read(root+'automation/paste/survey-request.cjs'));
 eval(read(root+'automation/paste/connection-policy.cjs'));
 eval(read(root+'automation/paste/native-air.cjs'));
 eval(read(root+'automation/paste/vacuum-baseline.cjs'));
 var q=JSON.parse(read(root+'automation/plans/paste-vacuum-probe-request.json')),
     jvm=Number(Java.type('java.lang.management.ManagementFactory').getRuntimeMXBean().getStartTime()),
     now=Number(java.lang.System.currentTimeMillis());
 PasteVacuumProbeNative.validate(q,now,jvm);
 function evidence(e,label){var f=new F(e.path);if(!f.isFile()||hash(Fs.readAllBytes(f.toPath()))!==e.sha256)throw Error(label+' evidence missing/changed');}
 evidence(q.stationaryEvidence,'Stationary');evidence(q.targetEvidence,'Target');evidence(q.jointEnvelopeEvidence,'Joint envelope');evidence(q.barrierEvidence,'Position barrier');
 var baselineBytes=Fs.readAllBytes(new F(q.baselineContractEvidence.path).toPath());if(hash(baselineBytes)!==q.baselineContractEvidence.sha256)throw Error('Baseline contract evidence missing/changed');var baselineRecord=JSON.parse(String(new java.lang.String(baselineBytes,UTF)));var baselineReference=PasteVacuumProbeNative.validateBaselineReference(baselineRecord,q,hash(baselineBytes));
 var barrierBytes=Fs.readAllBytes(new F(q.barrierEvidence.path).toPath());if(hash(barrierBytes)!==q.barrierEvidence.sha256)throw Error('Position barrier evidence changed');var barrierRecord=JSON.parse(String(new java.lang.String(barrierBytes,UTF)));
 var panel=Java.type('org.openpnp.gui.MainFrame').get().getJobTab(),state=panel.getClass().getDeclaredField('state');state.setAccessible(true);
 if(m.getDrivers().size()!==1)throw Error('Unexpected driver topology');var d=m.getDrivers().get(0);
 if(String(d.getClass().getName())!=='org.openpnp.machine.reference.driver.GcodeDriver'||String(d.getId())!=='DRV16982438146c1dd4')throw Error('Unknown driver');
 if(String(planner.getClass().getName())!=='org.openpnp.machine.reference.driver.NullMotionPlanner')throw Error('Only audited NullMotionPlanner allowed');
 var nativePositionAckTimeout=Number(privateValue('org.openpnp.machine.reference.driver.GcodeDriver','infinityTimeoutMilliseconds',d));if(!isFinite(nativePositionAckTimeout)||nativePositionAckTimeout<=0||nativePositionAckTimeout>60000)throw Error('Unbounded native position ACK timeout');
 var jar=new F(d.getClass().getProtectionDomain().getCodeSource().getLocation().toURI());if(hash(Fs.readAllBytes(jar.toPath()))!=='bcd34923ae91d61a96b98b4c82c93cdc90093ff94292270fd0a18fc6f96f7752')throw Error('Installed native API binary changed');
 var head=m.getDefaultHead(),left=head.getNozzleByName('N1'),right=head.getNozzleByName('N2'),top=head.getDefaultCamera(),bottom=null;
 for each(var camera in m.getCameras())if(String(camera.getLooking())==='Up'){if(bottom!==null)throw Error('Multiple bottom cameras');bottom=camera;}
 if(left==null||right==null||top==null||bottom==null||String(left.getId())!=='N1'||String(top.getId())!=='CAM1607555396816'||String(top.getLooking())!=='Down'||String(right.getId())!=='NOZ1710829fd33a0170')throw Error('Unexpected head/camera identity');
 var vac=head.getActuatorByName('VAC1');if(vac==null||String(vac.getId())!=='ACT171086c0660cfc3b'||vac.getDriver()!==d)throw Error('Expected VAC1 owner required');
 var items={N1:left,N2:right,top:top,bottom:bottom};
 function pose(n){var p=n.getLocation().convertToUnits(MM);return {x:Number(p.getX()),y:Number(p.getY()),z:Number(p.getZ()),rotation:Number(p.getRotation())};}
 function poses(){var x={};Object.keys(items).forEach(function(k){x[k]=pose(items[k]);});return x;}
 function comparePoses(a,b){Object.keys(items).forEach(function(k){['x','y','z','rotation'].forEach(function(v){if(typeof a[k][v]!=='number'||!isFinite(a[k][v])||typeof b[k][v]!=='number'||!isFinite(b[k][v])||Math.abs(a[k][v]-b[k][v])>0.0001)throw Error(k+' '+v+' changed unexpectedly/invalid');});});}
 var axes={},ids={X:'AXS169824381580efcb',Y:'AXS16982438158c4660',Z:'AXS16982438158d0458',A:'AXS16b068df4e35374e',B:'AXS17108288e61da5fb'};
 for each(var axis in new AL(m).drivenBy(d).getControllerAxes()){var L=String(axis.getLetter());if(!ids[L]||String(axis.getId())!==ids[L]||axes[L])throw Error('Unexpected raw controller axis');axes[L]=axis;}
 if(Object.keys(axes).sort().join(',')!=='A,B,X,Y,Z')throw Error('Missing raw axis');
 function snapshot(){var s={raw:{},driver:{},nativePoses:poses()};Object.keys(axes).forEach(function(k){s.raw[k]=Number(axes[k].getCoordinate());s.driver[k]=Number(axes[k].getDriverCoordinate());});return s;}
 function projectedPoses(raw){var result={};Object.keys(items).forEach(function(k){var n=items[k],location=n.getMappedAxes(m);Object.keys(axes).forEach(function(a){location=location.put(new AL(axes[a],raw[a]));});var p=n.toHeadMountableLocation(n.toTransformed(location)).convertToUnits(MM);result[k]={x:Number(p.getX()),y:Number(p.getY()),z:Number(p.getZ()),rotation:Number(p.getRotation())};});return result;}
 function verifyCoupledProjection(fromRaw,toRaw,fromPose,label){var a=projectedPoses(fromRaw),b=projectedPoses(toRaw),dz=toRaw.Z-fromRaw.Z;comparePoses(a,fromPose);Object.keys(items).forEach(function(k){['x','y','z','rotation'].forEach(function(v){if(typeof b[k][v]!=='number'||!isFinite(b[k][v]))throw Error(label+' invalid projected '+k+' '+v);});['x','y','rotation'].forEach(function(v){if(Math.abs(b[k][v]-a[k][v])>0.0001)throw Error(label+' changed '+k+' '+v);});var expect=a[k].z+(k==='N1'?dz:k==='N2'?-dz:0);if(Math.abs(b[k].z-expect)>0.0001)throw Error(label+' coupled Z polarity mismatch '+k);});return {start:a,target:b,rawDeltaZ:dz};}
 function nativeZConfiguration(){var z=axes.Z;return {softLowEnabled:!!z.isSoftLimitLowEnabled(),softLowMm:Number(z.getSoftLimitLow().convertToUnits(MM).getValue()),softHighEnabled:!!z.isSoftLimitHighEnabled(),softHighMm:Number(z.getSoftLimitHigh().convertToUnits(MM).getValue()),safeLowEnabled:!!z.isSafeZoneLowEnabled(),safeLowMm:Number(z.getSafeZoneLow().convertToUnits(MM).getValue()),safeHighEnabled:!!z.isSafeZoneHighEnabled(),safeHighMm:Number(z.getSafeZoneHigh().convertToUnits(MM).getValue())};}
 var originalReader=privateValue('org.openpnp.machine.reference.driver.GcodeDriver','readerThread',d),originalCommands=d.commands;
 function stateGate(){
  var rawZ=Number(axes.Z.getCoordinate());if(rawZ<q.contract.floorZmm-0.0001||rawZ>q.contract.startZmm+0.0001)throw Error('Current raw Z outside this request interval');
  var nz=nativeZConfiguration();Object.keys(nz).forEach(function(k){if(nz[k]!==q.nativeZConfiguration[k])throw Error('Native Z settings changed: '+k);});
  var min=Math.min(q.contract.startZmm,q.contract.floorZmm),max=Math.max(q.contract.startZmm,q.contract.floorZmm);if(nz.softLowEnabled&&min<nz.softLowMm||nz.softHighEnabled&&max>nz.softHighMm)throw Error('Full probe path violates enabled soft limits');
  if(d.commands!==originalCommands||originalReader==null||!originalReader.isAlive()||privateValue('org.openpnp.machine.reference.driver.GcodeDriver','readerThread',d)!==originalReader||privateValue('org.openpnp.machine.reference.driver.GcodeDriver','errorResponse',d)!=null)throw Error('Reader/commands changed or prior controller error');
  if((m.isBusy()&&!m.isTask(java.lang.Thread.currentThread()))||!m.isEnabled()||!m.isHomed()||String(state.get(panel))!=='Stopped')throw Error('Need idle enabled/homed machine and stopped job');
  if(String(privateValue('org.openpnp.machine.reference.driver.GcodeDriver','connected',d))!=='true'||d.isMotionPending())throw Error('Driver disconnected or motion pending');
  if(privateValue('org.openpnp.machine.reference.driver.AbstractMotionPlanner','motionCommands',planner).size()!==0)throw Error('Native motion queue not empty');
  var subordinate=privateValue('org.openpnp.machine.reference.driver.AbstractMotionPlanner','subordinateMotion',planner),subq=privateValue('org.openpnp.machine.reference.driver.AbstractMotionPlanner$SubordinateMotion','queue',subordinate);if(subq!=null&&!subq.isEmpty())throw Error('Subordinate motion queue not empty');
  for each(var h in m.getHeads())for each(var n in h.getNozzles())if(n.getPart()!=null||n.getPartsFeeder()!=null)throw Error('Held/associated part detected');
  if(right.getNozzleTip()!=null||right.getCompatibleNozzleTips().size()!==0||right.getRotationModeOffset()!=null||right.isChangerEnabled()||right.getManualNozzleTipChangeLocation().isInitialized()||m.getPnpJobProcessor().isPreRotateAllNozzles())throw Error('N2 quarantine changed');
  if(left.getNozzleTip()==null||String(left.getNozzleTip().getId())!==q.expectedLeftTipId)throw Error('N1 tip identity changed');
  for each(var actuator in head.getActuators())if(actuator.isInterlockActuator()||actuator.getInterlockMonitor()!=null)throw Error('Unexpected head actuator interlock');
  var mapped=[];for each(var ax in top.getMappedAxes(m).getControllerAxes()){mapped.push(String(ax.getLetter()));if(String(ax.getType())==='Rotation')throw Error('Top camera maps rotation');}if(mapped.sort().join(',')!=='X,Y')throw Error('Top camera must map only X/Y');
  var offsets=privateValue('org.openpnp.machine.reference.driver.AbstractMotionPlanner','lastDirectionalBacklashOffset',planner);for each(var a in offsets.getAxes())if(Math.abs(Number(offsets.getCoordinate(a)))>1e-9)throw Error('Directional compensation offset not zero');
  if(String(axes.Z.getType())!=='Z'||String(axes.Z.getBacklashCompensationMethod())!=='DirectionalCompensation'||Number(axes.Z.getBacklashOffset().convertToUnits(MM).getValue())!==0||Number(axes.Z.getSneakUpOffset().convertToUnits(MM).getValue())!==0)throw Error('Raw Z compensation differs from audited zero-offset settings');
  if(Number(axes.Z.getFeedratePerSecond().convertToUnits(MM).getValue())!==200||Number(planner.getMinimumSpeed())!==0.05)throw Error('Raw Z feed/minimum speed changed');
  var completeRegex=d.getCommand(top,CT.MOVE_TO_COMPLETE_REGEX);if(completeRegex!=null&&String(completeRegex).trim())throw Error('Native completion regex could hide response lines');
  var err=d.getCommand(null,CT.COMMAND_ERROR_REGEX);if(String(err)!==NativePasteAir.nativeErrorRegex)throw Error('Native full-response error latch absent/changed');
  PasteVacuumProbeNative.commandContract(d.getCommand(vac,CT.ACTUATE_BOOLEAN_COMMAND),d.getCommand(vac,CT.ACTUATOR_READ_COMMAND),d.getCommand(vac,CT.ACTUATOR_READ_REGEX),d.getCommand(null,CT.COMMAND_CONFIRM_REGEX),d.getCommand(top,CT.MOVE_TO_COMMAND),d.getCommand(top,CT.MOVE_TO_COMPLETE_COMMAND),d.getCommand(null,CT.GET_POSITION_COMMAND));
  if(String(d.getCommand(null,CT.POSITION_REPORT_REGEX))!=='^.*X:(?<X>-?\\d+\\.\\d+)\\s*Y:(?<Y>-?\\d+\\.\\d+)\\s*Z:(?<Z>-?\\d+\\.\\d+)\\s*A:(?<A>-?\\d+\\.\\d+)\\s*B:(?<B>-?\\d+\\.\\d+).*')throw Error('Position report regex changed');
 }
 stateGate();if(configHash()!==q.liveConfigurationSha256)throw Error('Live configuration hash changed');
 var executor=privateValue('org.openpnp.spi.base.AbstractMachine','executor',m);if(executor==null||executor.isShutdown()||executor.isTerminated()||executor.getCorePoolSize()!==1||executor.getMaximumPoolSize()!==1||executor.getActiveCount()!==0||!executor.getQueue().isEmpty())throw Error('Existing native executor must be idle; do not create a second');
 var taskSetter=Java.type('org.openpnp.spi.base.AbstractMachine').class.getDeclaredMethod('setTaskThread',Java.type('java.lang.Thread').class);taskSetter.setAccessible(true);function taskOwner(t){taskSetter.invoke(m,Java.to([t],'java.lang.Object[]'));}
 function settle(ms){if(!isFinite(ms)||ms<100||ms>2000)throw Error('Settle interval outside request contract');java.lang.Thread.sleep(ms);}
 function comparePoseMaps(a,b){comparePoses(a,b);}
 function equalStart(s,label){PasteSurveyRequest.compareExact(s.raw,q.expectedRaw,label+' raw');PasteSurveyRequest.compareExact(s.driver,q.expectedDriver,label+' driver');comparePoseMaps(s.nativePoses,q.expectedNativePoses);}
 var initial=snapshot();equalStart(initial,'expected start');
 var out=new F(root+'automation/evidence/paste-vacuum-probe-'+q.id);if(!out.mkdir())throw Error('Probe UUID already claimed');
 var r={schema:1,id:q.id,status:'claimed',startedAt:new Date().toISOString(),request:q,baselineReference:baselineReference,transitions:[],samples:[],baselineSamples:{off:[],on:[]},moves:[],commands:[],controllerQueries:[],vacuumState:null,motionSubmitted:false,controllerQuerySubmitted:false,transportUncertain:false,contactVerified:false,calibrationEstablished:false,noReplay:true,nativeMinimumSpeed:0.05,nativeZConfiguration:nativeZConfiguration(),positionQueryAckTimeoutMs:nativePositionAckTimeout,positionReportPollTimeoutMs:3000,controllerLineTimeoutMs:3000,nominalFeedCeilingMmS:10,rawStepsPerMm:40,rawStepsPerIncrement:2};
 function save(status){r.status=status;r.transitions.push({status:status,time:new Date().toISOString()});Fs.write(new F(out,'report.json').toPath(),bytes(JSON.stringify(r,null,2)+'\n'));}
 save('preflight-before-controller-query');
 var positionRegex='^.*X:(?<X>-?\\d+\\.\\d+)\\s*Y:(?<Y>-?\\d+\\.\\d+)\\s*Z:(?<Z>-?\\d+\\.\\d+)\\s*A:(?<A>-?\\d+\\.\\d+)\\s*B:(?<B>-?\\d+\\.\\d+).*',positionPattern=java.util.regex.Pattern.compile(positionRegex);
 function append(lines,to){for each(var ln in lines)to.push(String(ln.getLine()));}
 function checked(lines){PasteConnectionPolicy.responses(lines);lines.forEach(function(line){if(/unknown command|halted|fatal|\bkilled\b/i.test(line))throw Error('Controller fault: '+line);});}
 function collect(regex,entry){var got=d.receiveResponses(regex,3000,new (Java.type('org.openpnp.machine.reference.driver.GcodeDriver$TimeoutAction'))({apply:function(lines){append(lines,entry.responses);checked(entry.responses);entry.timedOut=true;save('bounded-response-timeout');throw new java.lang.Exception('Native response timeout; no retry');}}));append(got,entry.responses);checked(entry.responses);}
 var opStart=0;function deadline(){if(opStart&&Number(java.lang.System.currentTimeMillis())-opStart>q.contract.maxDurationMs)throw Error('Probe duration limit exceeded; no next command');}
 function freshM114(label,expectedZCountDelta){
  deadline();freshness();stateGate();var saved=snapshot(),expectedRaw=r.currentRaw||initial.raw,entry={label:label,savedBeforeQuery:saved,responses:[]};r.controllerQueries.push(entry);PasteVacuumProbeNative.compareAxes(saved.raw,expectedRaw,'M114 prequery raw');PasteVacuumProbeNative.compareAxes(saved.driver,expectedRaw,'M114 prequery driver');comparePoseMaps(saved.nativePoses,r.currentNativePoses||initial.nativePoses);
  append(d.receiveResponses(),entry.responses);checked(entry.responses);if(entry.responses.some(function(x){return positionPattern.matcher(x).matches();}))throw Error('Unclaimed stale M114 response');
  r.transportUncertain=true;r.controllerQuerySubmitted=true;save(label+'-M114-started');var observed=d.getReportedLocation(3000),reported={};for each(var a in observed.getControllerAxes())reported[String(a.getLetter())]=Number(observed.getCoordinate(a));
  collect(positionRegex,entry);var delim=-1;entry.responses.forEach(function(x,i){if(positionPattern.matcher(x).matches())delim=i;});if(delim<0)throw Error('Fresh position delimiter missing');if(!entry.responses.slice(delim+1).some(function(x){return /^ok/.test(x);}))collect('^ok.*',entry);append(d.receiveResponses(),entry.responses);checked(entry.responses);
  PasteVacuumProbeNative.compareAxes(reported,saved.raw,'M114 report/model');PasteVacuumProbeNative.compareAxes(reported,saved.driver,'M114 report/driver');entry.reported=reported;entry.stepCounts=PasteVacuumProbeNative.parseStepCount(entry.responses);if(r.lastVerifiedStepCounts)PasteVacuumProbeNative.compareOneStepCounts(r.lastVerifiedStepCounts,entry.stepCounts,'Z',expectedZCountDelta===undefined?0:expectedZCountDelta,'M114 controller counts');r.lastVerifiedStepCounts=entry.stepCounts;entry.savedAfterQuery=snapshot();PasteVacuumProbeNative.compareAxes(entry.savedAfterQuery.raw,saved.raw,'M114 postquery raw');comparePoseMaps(entry.savedAfterQuery.nativePoses,saved.nativePoses);entry.verified=true;r.transportUncertain=false;save(label+'-M114-verified');return entry;
 }
 function fixedLine(cmd,needsData){
  if(!PasteVacuumBaseline.allowedLine(cmd))throw Error('Command outside exact VAC1 template allowlist');deadline();freshness();stateGate();var before=snapshot();PasteVacuumProbeNative.compareAxes(before.raw,r.currentRaw||initial.raw,'VAC command raw');comparePoseMaps(before.nativePoses,r.currentNativePoses||initial.nativePoses);if(!executor.getQueue().isEmpty())throw Error('Competing native task queued');
  var stale=[];append(d.receiveResponses(),stale);checked(stale);if(stale.length)throw Error('Unexpected unsolicited response before VAC1 command');
  var e={command:cmd,startedMs:Number(java.lang.System.currentTimeMillis()),responses:[],acknowledged:false};r.commands.push(e);r.transportUncertain=true;save('sending-reviewed-vac1-line');d.sendCommand(cmd,3000);collect('^ok.*',e);if(needsData&&!e.responses.some(function(x){return /data:/.test(x);}))collect('^.*data:.*',e);append(d.receiveResponses(),e.responses);checked(e.responses);e.value=PasteVacuumProbeNative.parseSensorResponse(e.responses,needsData);e.finishedMs=Number(java.lang.System.currentTimeMillis());e.acknowledged=true;r.transportUncertain=false;save('reviewed-vac1-line-acknowledged');deadline();return e.value;
 }
 function actuate(on){r.actuationSubmitted=true;r.actuationPending=true;r.requestedVacuumOn=on;save('vac1-actuation-started');var lines=PasteVacuumBaseline.actuationLines(on);lines.forEach(function(x){fixedLine(x,false);});r.actuationPending=false;r.vacuumState=on?'on':'off';r.vacuumStateAcknowledged=true;r.actuationCacheNotUpdated=true;save(on?'vacuum-on-acknowledged':'vacuum-off-acknowledged');}
 function readSensor(){var lines=PasteVacuumBaseline.sensorLines(),v=null;lines.forEach(function(x,i){v=fixedLine(x,i===lines.length-1);});return v;}
 function capture(camera,name){if(String(camera.getClass().getName())!=='org.openpnp.machine.reference.camera.OpenPnpCaptureCamera')throw Error('Unknown camera implementation');var open=camera.getClass().getDeclaredMethod('isOpen');open.setAccessible(true);if(!open.invoke(camera))throw Error('Camera stream not already open');var image=camera.captureRaw();if(image==null||!I.write(image,'png',new F(out,name+'.png')))throw Error('Raw camera capture failed');return {path:name+'.png',width:image.getWidth(),height:image.getHeight()};}
 function verifyBarrier(at){var raw=Fs.readAllBytes(new F(q.barrierEvidence.path).toPath());if(hash(raw)!==q.barrierEvidence.sha256)throw Error('Position barrier evidence changed');barrierRecord=JSON.parse(String(new java.lang.String(raw,UTF)));return PasteVacuumProbeNative.barrier(barrierRecord,q,at,jvm);}
 function freshness(){var t=Number(java.lang.System.currentTimeMillis());PasteVacuumProbeNative.validate(q,t,jvm);verifyBarrier(t);}
 freshness();
 var policyConfig={responseDirection:q.contract.responseDirection,startZmm:q.contract.startZmm,minZmm:q.contract.floorZmm,stepMm:q.contract.stepMm,maxDescentMm:q.contract.maxDescentMm,baselineSamples:q.contract.baselineSamples,baselineTolerance:q.contract.baselineTolerance,noiseFloor:q.contract.noiseFloor,candidateMinDelta:q.contract.candidateMinDelta,samplesToConfirm:q.contract.samplesToConfirm,sampleIntervalMinMs:q.contract.sampleIntervalMinMs,sampleIntervalMaxMs:q.contract.sampleIntervalMaxMs,maxDurationMs:q.contract.maxDurationMs};
 var policy=null,stepIndex=0,baselineRows=[];
 function ownedSamples(){
  var decision=null;
  while(!decision||decision.decision==='collect-fresh-empty-baseline'||decision.decision==='hold-z-confirm-deviation'||decision.decision==='hold-z-confirm-no-deviation'){
   if(decision&&decision.decision==='collect-fresh-empty-baseline'&&policy.phase==='awaiting-move')return decision;
   if(decision&&decision.decision.indexOf('hold-z')===0&&policy.phase==='candidate')return decision;
   settle(policy.phase==='baseline'?q.contract.baselineIntervalMinMs:q.contract.sampleIntervalMinMs);
   var query=freshM114('sample-'+r.samples.length);var value=readSensor();var at=Number(java.lang.System.currentTimeMillis()),s={index:r.samples.length,value:value,zmm:Number(axes.Z.getCoordinate()),timestampMs:at,elapsedMs:at-opStart,m114QueryIndex:r.controllerQueries.length-1,preQuerySnapshot:query.savedBeforeQuery};r.samples.push(s);if(policy.phase==='baseline')r.baselineSamples.on.push({value:value,timestampMs:at,elapsedMs:at-opStart,m114QueryIndex:r.controllerQueries.length-1,preQuerySnapshot:query.savedBeforeQuery});save('sample-recorded');
   decision=VacuumProbePolicy.sample(policy,value,at);s.decision=decision.decision;s.policyPhase=policy.phase;save('policy-'+decision.decision);
   if(decision.decision==='abort')throw Error('Probe policy stopped: '+decision.reason);
   if(decision.decision==='seal-candidate-stop-and-hold-z'){r.sealCandidate={zmm:decision.zmm,baseline:decision.baseline,deltas:decision.deltas,contactVerified:false};save('seal-candidate-hold-z');return decision;}
  }
  return decision;
 }
 function moveOne(decision){
  if(!r.freshBaselineGate)throw Error('Fresh vacuum-off/on/pump gate must pass before any Z move');if(decision.nextZmm==null||policy.phase!=='awaiting-move')throw Error('Policy did not request a move');var targetZ=decision.nextZmm,expect=PasteVacuumProbeNative.target(q.contract.startZmm,0.05,stepIndex);if(Math.abs(targetZ-expect)>1e-9||targetZ<q.contract.floorZmm-1e-9||q.contract.startZmm-targetZ>2.0000001)throw Error('Policy/native target mismatch or 2 mm cap');
  deadline();freshness();stateGate();if(configHash()!==q.liveConfigurationSha256)throw Error('Live configuration changed before Z move');if(!executor.getQueue().isEmpty())throw Error('Competing native task queued immediately before Z move');var before=snapshot();PasteVacuumProbeNative.compareAxes(before.raw,r.currentRaw||initial.raw,'pre-move raw');comparePoses(before.nativePoses,r.currentNativePoses||initial.nativePoses);if(Math.abs(before.raw.Z-policy.zmm)>0.0001)throw Error('Verified raw Z differs from policy state');var exp={X:before.raw.X,Y:before.raw.Y,Z:targetZ,A:before.raw.A,B:before.raw.B};var loc=new AL(axes.Z,targetZ);if(loc.getControllerAxes().size()!==1||!loc.contains(axes.Z)||Math.abs(Number(loc.getCoordinate(axes.Z))-targetZ)>1e-9)throw Error('Exactly one raw-Z target required');if(!planner.isValidLocation(top,loc))throw Error('Native planner rejects raw Z step');var stepProjection=verifyCoupledProjection(before.raw,exp,before.nativePoses,'one-step pre-move projection');
  var beforeNative=before.nativePoses,startZ=Number(before.raw.Z),dz=targetZ-startZ,expectedNative={};Object.keys(items).forEach(function(k){expectedNative[k]={};['x','y','z','rotation'].forEach(function(a){expectedNative[k][a]=beforeNative[k][a]+(a==='z'?(k==='N1'?dz:k==='N2'?-dz:0):0);});});
  Object.keys(items).forEach(function(k){['x','y','z','rotation'].forEach(function(a){if(Math.abs(expectedNative[k][a]-beforeNative[k][a])>0.050001)throw Error('Native coupled movement exceeds one increment');});});
  r.currentNativePoses=beforeNative;r.preMoveSnapshot=before;r.preMoveCoupledProjection=stepProjection;r.expectedAfterRaw=exp;r.motionSubmitted=true;r.transportUncertain=true;r.controllerPositionVerified=false;save('submitting-one-native-raw-z-step');planner.moveTo(top,loc,0.05,MO.SpeedOverPrecision);r.nativeMotionCompletionReported=true;save('native-stillstand-reported');
  var after=snapshot();PasteSurveyRequest.compareExact(after.raw,exp,'postmove model');Object.keys(items).forEach(function(k){['x','y','z','rotation'].forEach(function(a){if(Math.abs(after.nativePoses[k][a]-expectedNative[k][a])>0.0001)throw Error('Coupled native Z polarity mismatch '+k+' '+a);});});r.currentRaw=after.raw;r.currentNativePoses=after.nativePoses;
  var qrec=freshM114('postmove-'+stepIndex,-2);PasteVacuumProbeNative.compareAxes(qrec.reported,exp,'postmove firmware');r.moves.push({index:stepIndex,fromZ:startZ,targetZ:targetZ,verifiedRaw:after.raw,reported:qrec.reported,stepCounts:qrec.stepCounts,nativeBefore:beforeNative,nativeAfter:after.nativePoses,nativeStillstandReported:true,feedFraction:0.05,nominalFeedCeilingMmS:10});r.controllerPositionVerified=true;r.transportUncertain=false;save('one-step-position-verified');
  stepIndex++;decision=VacuumProbePolicy.acknowledgeZMove(policy,targetZ,Number(java.lang.System.currentTimeMillis()));if(decision.decision!=='move-acknowledged-sample-at-current-z')throw Error('Policy rejected independently verified native step');return decision;
 }
 save('queued-on-existing-native-executor');
 try{executor.submit(new (Java.type('java.util.concurrent.Callable'))({call:function(){
  var owned=false,keepBusy=false;
  try{
   if(m.isBusy()||!executor.getQueue().isEmpty())throw Error('Native task ownership changed before probe');taskOwner(java.lang.Thread.currentThread());owned=true;m.fireMachineBusy(true);
   freshness();stateGate();if(configHash()!==q.liveConfigurationSha256)throw Error('Live configuration changed before task');equalStart(snapshot(),'queued start');
   var fullEnd={X:initial.raw.X,Y:initial.raw.Y,Z:q.contract.floorZmm,A:initial.raw.A,B:initial.raw.B};r.fullCoupledZProjection=verifyCoupledProjection(initial.raw,fullEnd,initial.nativePoses,'full reviewed N1-down/N2-up interval');save('full-coupled-projection-verified');
   var firstQuery=freshM114('before');r.lastVerifiedStepCounts=firstQuery.stepCounts;settle(200);r.beforeImages={top:capture(top,'top-before-raw'),bottom:capture(bottom,'bottom-before-raw')};save('fresh-images-captured');
   freshness();stateGate();if(configHash()!==q.liveConfigurationSha256)throw Error('Live config changed during camera preflight');
   // Whole operation deadline starts before the first native VAC1 command.
   opStart=Number(java.lang.System.currentTimeMillis());policy=VacuumProbePolicy.createProbe(policyConfig,opStart);
   actuate(false);settle(500);r.vacuumOffBaselineStarted=true;save('collecting-three-fresh-vacuum-off-baseline-samples');for(var oi=0;oi<q.contract.offBaselineSamples;oi++){if(oi>0)settle(q.contract.baselineIntervalMinMs);var oq=freshM114('vacuum-off-baseline-'+oi),ov=readSensor(),ot=Number(java.lang.System.currentTimeMillis());r.baselineSamples.off.push({index:oi,value:ov,timestampMs:ot,elapsedMs:ot-opStart,m114QueryIndex:r.controllerQueries.length-1,preQuerySnapshot:oq.savedBeforeQuery});save('fresh-vacuum-off-baseline-sample-recorded');}
   actuate(true);settle(500);r.vacuumOnBaselineStarted=true;save('collecting-fresh-empty-vacuum-on-baseline');
   var decision=ownedSamples();if(policy.phase==='awaiting-move'){r.freshBaselineGate=PasteVacuumProbeNative.validateFreshBaselines(r.baselineSamples.off.map(function(x){return x.value;}),r.baselineSamples.on.map(function(x){return x.value;}),q.contract);save('fresh-off-on-pump-baseline-gate-passed');
    while(true){decision=moveOne(decision);decision=ownedSamples();if(decision.decision==='seal-candidate-stop-and-hold-z')break;if(policy.phase==='stopped')throw Error('Probe reached fail-closed terminal policy state');}
   }
   if(decision.decision!=='seal-candidate-stop-and-hold-z'||r.transportUncertain)throw Error('No confirmed stationary seal candidate');
   // Release only after confirmed candidate and known stationary transport;
   // intentionally no retreat/lift, retry, compression, or safe-Z operation.
   stateGate();if(!r.controllerPositionVerified)throw Error('Final position not independently verified');actuate(false);r.normalVacuumOffAcknowledged=r.vacuumState==='off'&&r.vacuumStateAcknowledged===true;r.contactVerified=false;r.calibrationEstablished=false;r.uncertainCompletion=false;r.finishedAt=new Date().toISOString();save('completed-seal-candidate-held-at-z-awaiting-physical-review');
  }catch(e){r.error=String(e);r.uncertainCompletion=r.transportUncertain===true||(r.motionSubmitted&&!r.controllerPositionVerified);r.auditIncomplete=true;r.noAutomaticVacuumOffOnFault=true;r.noAutomaticLiftOrRecovery=true;r.finishedAt=new Date().toISOString();
   if(r.motionSubmitted||r.controllerQuerySubmitted||r.actuationPending||r.transportUncertain){keepBusy=true;r.queuedTasksCancelled=0;var pending;while((pending=executor.getQueue().poll())!=null){if(pending instanceof Java.type('java.util.concurrent.Future'))pending.cancel(false);r.queuedTasksCancelled++;}executor.shutdown();r.executorQuarantined=true;r.faultGateScope='Retained busy marker/stopped executor blocks reviewed dispatcher and busy-sensitive UI only; direct UI/native submissions may bypass. Operator must supervise stop/recovery; no automatic VAC1 off or motion after fault.';}
   save('failed-closed-no-retry-no-off-no-lift');
  }finally{if(owned&&!keepBusy){taskOwner(null);m.fireMachineBusy(false);}print(String(out));}return null;
 }}));}catch(e){r.error=String(e);r.uncertainCompletion=false;save('enqueue-failed-no-motion');throw e;}
})();
