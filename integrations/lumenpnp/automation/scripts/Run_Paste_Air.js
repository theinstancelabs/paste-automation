// STAGED, NOT COMMISSIONED. Never executes fork G-code or opens a connection.
// Remove this code gate only after independent native tool-exclusion validation.
var PASTE_PHYSICAL_EXECUTION_ENABLED = false;
(function(){
 var C=Java.type('org.openpnp.model.Configuration'), U=Java.type('org.openpnp.util.UiUtils'),
 T=Java.type('org.openpnp.util.UiUtils.Thrunnable'), F=Java.type('java.io.File'), Fs=Java.type('java.nio.file.Files'),
 Opt=Java.type('java.nio.file.StandardOpenOption'), L=Java.type('org.openpnp.model.Location'),
 MM=Java.type('org.openpnp.model.LengthUnit').Millimeters, Still=Java.type('org.openpnp.spi.MotionPlanner$CompletionType').WaitForStillstand,
 System=Java.type('java.lang.System');
 var root='/home/lumen/lumenpnp/', dir=root+'automation/plans/', outBase=root+'automation/evidence/';
 function read(path){return String(new java.lang.String(Fs.readAllBytes(new F(path).toPath()),'UTF-8'));}
 function json(path){return JSON.parse(read(path));}
 function hash(text){var bytes=Java.type('java.security.MessageDigest').getInstance('SHA-256').digest(new java.lang.String(text).getBytes('UTF-8')),s='';for(var i=0;i<bytes.length;i++)s+=('0'+((bytes[i]&255).toString(16))).slice(-2);return s;}
 function write(path,obj,fresh){Fs.write(new F(path).toPath(),new java.lang.String(JSON.stringify(obj,null,2)+'\n').getBytes('UTF-8'),fresh?Java.to([Opt.CREATE_NEW,Opt.WRITE],'java.nio.file.OpenOption[]'):Java.to([Opt.CREATE,Opt.TRUNCATE_EXISTING,Opt.WRITE],'java.nio.file.OpenOption[]'));}
 if(!PASTE_PHYSICAL_EXECUTION_ENABLED)throw Error('Paste physical execution disabled: native exclusion and installed right-head clearance are not commissioned');
 eval(read(root+'automation/paste/safety.cjs'));
 var body=read(dir+'paste-air-plan.json'), b=JSON.parse(body), s=json(dir+'paste-session.json');
 var jvm=Number(Java.type('java.lang.management.ManagementFactory').getRuntimeMXBean().getStartTime());
 PasteSafety.session(s,b,hash(body),Number(System.currentTimeMillis()),jvm);
 var m=C.get().getMachine();
 if(m.isBusy())throw Error('Machine busy; no queued paste request permitted');
 var panel=Java.type('org.openpnp.gui.MainFrame').get().getJobTab();
 var state=panel.getClass().getDeclaredField('state');state.setAccessible(true);
 if(String(state.get(panel))!=='Stopped')throw Error('Placement job must be stopped, including no paused job');
 // Claim before queueing. Existing record (including preflight failure) forbids replay.
 var out=new F(outBase+'paste-air-'+b.id);if(!out.mkdir())throw Error('Plan already claimed; never retry/replay it');
 write(out+'/plan.json',b,true);write(out+'/session.json',s,true);
 var r={id:b.id,mode:'air',physicalValidation:false,startedAt:new Date().toISOString(),status:'claimed',completedPoints:0,transitions:[],uncertainCompletion:false};
 function record(status){r.status=status;r.transitions.push({status:status,time:new Date().toISOString(),completedPoints:r.completedPoints});write(out+'/record.json',r,false);}
 function nozzle(id){for each(var h in m.getHeads())for each(var n in h.getNozzles())if(String(n.getId())===id)return n;throw Error('Nozzle id missing '+id);}
 function pose(n){var l=n.getLocation().convertToUnits(MM);return {x:Number(l.getX()),y:Number(l.getY()),z:Number(l.getZ()),rotation:Number(l.getRotation())};}
 function compare(actual,expected,label){['x','y','z','rotation'].forEach(function(k){PasteSafety.near(actual[k],expected[k],label+' '+k);});}
 function control(){var f=new F(dir+'paste-control.json');if(!f.exists())return null;var q=json(String(f));if(q.planId!==b.id)throw Error('Stale/foreign paste control file');if(q.action!=='pause'&&q.action!=='cancel')throw Error('Invalid paste control');return q.action;}
 record('queued');
 U.submitUiMachineTask(new T({thrun:function(){
  var inFlight=false;
  try{
   PasteSafety.session(s,b,hash(body),Number(System.currentTimeMillis()),jvm);
   if(!m.isHomed()||!m.isEnabled()||String(state.get(panel))!=='Stopped')throw Error('Need enabled homed idle machine with stopped job');
   var left=nozzle(b.profile.leftNozzleId), right=nozzle(b.profile.rightNozzleId);
   if(String(right.getName())!=='N2'||String(left.getName())!=='N1')throw Error('Unexpected nozzle identity');
   if(left.getHead()!==right.getHead())throw Error('Unexpected head topology');
   for each(var h in m.getHeads())for each(var n in h.getNozzles())if(n.getPart()!=null)throw Error('Held part on machine');
   // Legacy N24 runout/rotation/tool-change representation must not be used.
   if(right.getNozzleTip()!=null||right.getCompatibleNozzleTips().size()!==0||right.isChangerEnabled()||right.getRotationModeOffset()!=null)throw Error('Right head still has placement/tool-change configuration');
   if(m.getPnpJobProcessor().isPreRotateAllNozzles())throw Error('Global nozzle pre-rotation is still enabled');
   if(String(left.getHeadOffsets())!==b.profile.leftHeadOffsets||String(right.getHeadOffsets())!==b.profile.rightHeadOffsets)throw Error('Measured head offsets changed');
   right.waitForCompletion(Still);
   compare(pose(left),s.start.left,'left start');compare(pose(right),s.start.right,'right start');
   var liveWriter=new java.io.StringWriter();C.createSerializer().write(m,liveWriter);
   if(hash(String(liveWriter))!==b.profile.liveConfigurationSha256)throw Error('Live native configuration changed since measured profile (includes axis mappings/driver commands)');
   var start=right.getLocation().convertToUnits(MM), initialRaw=right.toRaw(right.toHeadLocation(start)), targets=[];
   // Preflight EVERY native transform before first submission. Bounds are raw
   // controller values, independent of native N2 display-frame bounds.
   function checkRaw(raw){
    var types={};
    for each(var axis in raw.getControllerAxes()){
     var value=Number(raw.getCoordinate(axis)), type=String(axis.getType()), id=String(axis.getId());
     types[type]=true;
     if(type!=='X'&&type!=='Y')PasteSafety.near(value,Number(initialRaw.getCoordinate(axis)),'non-XY controller axis '+id);
     else {var limits=b.profile.rawBounds[id];if(!limits)throw Error('No measured controller bounds '+id);PasteSafety.bound(value,limits.min,limits.max,'raw '+id);}
    }
    if(!types.X||!types.Y||!types.Z||!types.Rotation)throw Error('Unexpected native raw axis topology');
   }
   checkRaw(initialRaw);
   for(var i=0;i<b.points.length;i++){
    var target=new L(MM,b.points[i].x,b.points[i].y,start.getZ(),start.getRotation());
    if(!right.isReachable(target))throw Error('Native target unreachable '+i);
    checkRaw(right.toRaw(right.toHeadLocation(target)));targets.push(target);
   }
   record('preflight-complete-at-joint-clearance');
   for(var i=0;i<targets.length;i++){
    var stop=control();if(stop){record(stop==='pause'?'paused-at-clearance':'cancelled-at-clearance');return;}
    if(!m.isEnabled()||!m.isHomed())throw Error('Machine state lost; do not replay');
    PasteSafety.near(pose(left).z,b.profile.leftClearanceZ,'left clearance');PasteSafety.near(pose(right).z,b.profile.safeZ,'right clearance');
    checkRaw(right.toRaw(right.toHeadLocation(targets[i])));
    record('moving-point-'+i);inFlight=true;
    // Only native XY. OpenPnP substitutes unchanged Z/rotation, handles its own
    // coordinate transforms, speed limits, driver ownership and completion.
    right.moveTo(new L(MM,targets[i].getX(),targets[i].getY(),NaN,NaN),b.profile.speedFraction);
    right.waitForCompletion(Still);inFlight=false;
    var actual=pose(right);PasteSafety.near(actual.x,b.points[i].x,'completed X');PasteSafety.near(actual.y,b.points[i].y,'completed Y');
    PasteSafety.near(actual.z,s.start.right.z,'completed right Z');PasteSafety.near(actual.rotation,s.start.right.rotation,'completed right rotation');
    PasteSafety.near(pose(left).z,s.start.left.z,'completed left Z');PasteSafety.near(pose(left).rotation,s.start.left.rotation,'completed left rotation');
    r.completedPoints=i+1;record('point-complete-at-clearance');
   }
   var stop=control();record(stop?(stop==='pause'?'paused-at-clearance':'cancelled-at-clearance'):'completed-air-software');
  }catch(e){r.error=String(e);r.uncertainCompletion=inFlight;r.noReplay=true;record('fault-no-recovery-motion');throw e;}
 }}));
})();
