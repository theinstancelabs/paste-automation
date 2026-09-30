// Capture-only software snapshot. No connection, serial query, camera acquisition,
// camera reopen, motion, homing, actuation, offset correction or configuration save.
(function(){
 var C=Java.type('org.openpnp.model.Configuration'), F=Java.type('java.io.File'), Fs=Java.type('java.nio.file.Files'),
 MM=Java.type('org.openpnp.model.LengthUnit').Millimeters, MD=Java.type('java.security.MessageDigest'),
 UTF8=Java.type('java.nio.charset.StandardCharsets').UTF_8, Arrays=Java.type('java.util.Arrays');
 var root='/home/lumen/lumenpnp/', cfg=C.get(), m=cfg.getMachine();
 function read(path){return String(new java.lang.String(Fs.readAllBytes(new F(path).toPath()),UTF8));}
 function bytes(s){return new java.lang.String(s).getBytes(UTF8);}
 function hash(data){var d=MD.getInstance('SHA-256').digest(data),s='';for(var i=0;i<d.length;i++)s+=('0'+((d[i]&255).toString(16))).slice(-2);return s;}
 function write(file,obj){Fs.write(file.toPath(),bytes(JSON.stringify(obj,null,2)+'\n'));}
 if(m.isBusy())throw Error('Busy machine: measurement snapshot refused');
 var panel=Java.type('org.openpnp.gui.MainFrame').get().getJobTab(), state=panel.getClass().getDeclaredField('state');state.setAccessible(true);
 if(String(state.get(panel))!=='Stopped')throw Error('Placement job must be stopped for measurement snapshot');
 eval(read(root+'automation/paste/measurement-request.cjs'));
 var body=read(root+'automation/plans/paste-measurement-request.json'), q=JSON.parse(body);
 var jvm=Number(Java.type('java.lang.management.ManagementFactory').getRuntimeMXBean().getStartTime());
 PasteMeasurementRequest.validate(q,Number(java.lang.System.currentTimeMillis()),jvm);
 var evidence=[];
 function fileEvidence(path,kind){var f=new F(path);if(!f.isFile()||!f.canRead())throw Error('Missing/unreadable existing evidence '+path);return {kind:kind,path:String(f.getCanonicalPath()),sha256:hash(Fs.readAllBytes(f.toPath())),sizeBytes:Number(f.length()),modifiedMs:Number(f.lastModified()),meaning:'Referenced existing file; not proof of target observation or current physical state'};}
 for(var e=0;e<q.evidencePaths.length;e++)evidence.push(fileEvidence(q.evidencePaths[e],'operator-supplied'));
 if(q.firmwareQueryRecord!==null)evidence.push(fileEvidence(q.firmwareQueryRecord,'firmware-query-reference'));
 var out=new F(root+'automation/evidence/paste-measurement-'+q.id);if(!out.mkdir())throw Error('Measurement id already claimed; use a fresh request, never overwrite');
 var report={schema:1,id:q.id,startedAt:new Date().toISOString(),jvmStartMs:jvm,requestSha256:hash(bytes(body)),status:'capturing',calibrationEstablished:false,physicalValidation:false,
   enabled:m.isEnabled(),homed:m.isHomed(),coordinateValidity:m.isHomed()?'software-homed-only-physical-verification-required':'unhomed-software-coordinates-not-calibration',
   sampleRole:q.sampleRole,target:q.target,operator:q.operator,operatorObservedTarget:q.operatorObservedTarget===true,evidence:evidence,
   operatorSuppliedPhysicalMeasurements:q.physicalMeasurements,notes:q.notes||'',nozzles:[],cameras:[]};
 function save(){write(new F(out,'report.json'),report);}
 function pose(item){var l=item.getLocation().convertToUnits(MM),p={x:Number(l.getX()),y:Number(l.getY()),z:Number(l.getZ()),rotation:Number(l.getRotation()),units:'Millimeters',source:'OpenPnP model only; no controller position query'};['x','y','z','rotation'].forEach(function(k){if(!isFinite(p[k]))throw Error('Nonfinite software pose '+String(item.getId())+' '+k);});return p;}
 write(new F(out,'request.json'),q);save();
 try{
  var backup=new F(root+'.local-machine-backups/paste-measurement-'+q.id);if(!backup.mkdir())throw Error('Private measurement backup already exists or cannot be created');
  var sw=new java.io.StringWriter();C.createSerializer().write(m,sw);var live=bytes(String(sw)), snapshot=new F(backup,'live-machine.xml');Fs.write(snapshot.toPath(),live);
  if(!Arrays.equals(live,Fs.readAllBytes(snapshot.toPath())))throw Error('Live snapshot byte verification failed');
  report.liveConfiguration={path:String(snapshot),sha256:hash(live),kind:'Serialized live machine, not saved configuration and not physical calibration'};
  var disk=new F(cfg.getConfigurationDirectory(),'machine.xml');if(disk.isFile())report.savedConfiguration={path:String(disk),sha256:hash(Fs.readAllBytes(disk.toPath())),kind:'Read-only disk hash; may differ from live snapshot'};
  var cameraIds={};function camera(c,headId){var id=String(c.getId());if(cameraIds[id])return;cameraIds[id]=true;report.cameras.push({id:id,name:String(c.getName()),headId:headId,pose:pose(c),headOffsets:String(c.getHeadOffsets())});}
  for each(var h in m.getHeads()){
   for each(var n in h.getNozzles())report.nozzles.push({id:String(n.getId()),name:String(n.getName()),headId:String(h.getId()),pose:pose(n),headOffsets:String(n.getHeadOffsets()),tip:n.getNozzleTip()==null?null:String(n.getNozzleTip().getId()),part:n.getPart()==null?null:String(n.getPart().getId())});
   for each(var c in h.getCameras())camera(c,String(h.getId()));
  }
  for each(var c in m.getCameras())camera(c,null);
  if(m.isBusy()||m.isEnabled()!==report.enabled||m.isHomed()!==report.homed||String(state.get(panel))!=='Stopped')throw Error('Machine state changed during snapshot; discard sample for measurement use');
  report.status='captured-software-only';report.finishedAt=new Date().toISOString();save();print('Paste measurement software snapshot: '+out+' (calibrationEstablished=false)');
 }catch(err){report.status='failed-incomplete';report.error=String(err);report.finishedAt=new Date().toISOString();save();throw err;}
})();
