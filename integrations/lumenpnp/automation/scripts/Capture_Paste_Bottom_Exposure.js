// Stationary existing-camera exposure bracket. Parent dispatch only after review.
// No machine task, controller command, light actuator, motion or configuration save.
(function(){
 var C=Java.type('org.openpnp.model.Configuration'),F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8,
 AL=Java.type('org.openpnp.model.AxesLocation'),I=Java.type('javax.imageio.ImageIO'),MD=Java.type('java.security.MessageDigest');
 var m=C.get().getMachine(),planner=m.getMotionPlanner(),bottom=null;
 function field(c,n,o){var f=Java.type(c).class.getDeclaredField(n);f.setAccessible(true);return f.get(o);}
 function bytes(s){return new java.lang.String(s).getBytes(UTF);}
 function hash(data){var a=MD.getInstance('SHA-256').digest(data),s='';for(var i=0;i<a.length;i++)s+=('0'+((a[i]&255).toString(16))).slice(-2);return s;}
 function configHash(){var w=new java.io.StringWriter();C.createSerializer().write(m,w);return hash(bytes(String(w)));}
 var panel=Java.type('org.openpnp.gui.MainFrame').get().getJobTab(),state=panel.getClass().getDeclaredField('state');state.setAccessible(true);
 if(m.getDrivers().size()!==1)throw Error('Single existing driver required');var driver=m.getDrivers().get(0);
 function snapshot(){var a={};for each(var axis in new AL(m).drivenBy(driver).getControllerAxes())a[String(axis.getLetter())]={model:Number(axis.getCoordinate()),driver:Number(axis.getDriverCoordinate())};return a;}
 var initial=snapshot();if(Object.keys(initial).sort().join(',')!=='A,B,X,Y,Z')throw Error('Full stationary XYZAB snapshot required');
 function gate(){
  if(m.isBusy()||String(state.get(panel))!=='Stopped'||driver.isMotionPending())throw Error('Idle stationary machine and stopped job required');
  var e=field('org.openpnp.spi.base.AbstractMachine','executor',m);
  if(e!=null&&(e.isShutdown()||e.isTerminated()||e.getActiveCount()!==0||!e.getQueue().isEmpty()))throw Error('Native executor not idle');
  if(field('org.openpnp.machine.reference.driver.AbstractMotionPlanner','motionCommands',planner).size()!==0)throw Error('Native motion queued');
  if(JSON.stringify(snapshot())!==JSON.stringify(initial))throw Error('Stationary raw/driver snapshot changed');
 }
 gate();for each(var camera in m.getCameras())if(String(camera.getLooking())==='Up'){if(bottom!==null)throw Error('Multiple bottom cameras');bottom=camera;}
 if(bottom==null||String(bottom.getId())!=='CAM1614803235898'||String(bottom.getClass().getName())!=='org.openpnp.machine.reference.camera.OpenPnpCaptureCamera')throw Error('Exact existing bottom capture camera required');
 var open=bottom.getClass().getDeclaredMethod('isOpen');open.setAccessible(true);if(!open.invoke(bottom))throw Error('Camera stream must already be open; no reopen');
 var exposure=bottom.getExposure();if(!exposure.isSupported())throw Error('Exposure unsupported');
 var oldValue=Number(exposure.getValue()),oldAuto=exposure.isAuto(),low=Number(exposure.getMin()),high=Number(exposure.getMax());
 if(!isFinite(oldValue)||oldValue<low||oldValue>high||oldValue<=0)throw Error('Unreviewed exposure range/current value');
 // Numeric property verification is exact when manual; do not claim a fixed
 // numerical restore for automatic exposure, whose value can change itself.
 if(oldAuto)throw Error('Existing exposure must be manual for exact restoration');
 var values=[];[16,32,64,128].forEach(function(divisor){var value=Math.max(low,Math.floor(oldValue/divisor));if(value<oldValue&&values.indexOf(value)<0)values.push(value);});
 if(!values.length)throw Error('No lower exposure available');
 var beforeHash=configHash(),out=new F('/home/lumen/lumenpnp/automation/evidence/paste-bottom-exposure-'+java.lang.System.currentTimeMillis());if(!out.mkdir())throw Error('Unique evidence directory required');
 var r={scope:'stationary-bottom-camera-exposure-bracket',status:'started',jvmStartMs:Number(Java.type('java.lang.management.ManagementFactory').getRuntimeMXBean().getStartTime()),startedAt:new Date().toISOString(),liveConfigurationBeforeSha256:beforeHash,beforeSnapshot:initial,originalExposure:oldValue,originalAuto:oldAuto,exposureRange:[low,high],plannedExposures:values,images:[],noControllerCommands:true,noMotion:true,configurationSaved:false,physicalCalibrationEstablished:false};
 function save(){Fs.write(new F(out,'report.json').toPath(),bytes(JSON.stringify(r,null,2)+'\n'));}
 function capture(label){gate();if(!open.invoke(bottom))throw Error('Camera stream closed');var image=bottom.captureRaw(),file=new F(out,label+'.png');if(image==null||!I.write(image,'png',file))throw Error('Raw bottom capture failed');r.images.push({path:String(file.getName()),sha256:hash(Fs.readAllBytes(file.toPath())),exposure:Number(exposure.getValue()),auto:exposure.isAuto(),width:image.getWidth(),height:image.getHeight()});save();}
 save();var failure=null;
 try{
  capture('original');
  values.forEach(function(value){gate();exposure.setValue(value);if(Number(exposure.getValue())!==value||exposure.isAuto())throw Error('Camera exposure setter not verified');java.lang.Thread.sleep(700);capture('exposure-'+value);});
 }catch(error){failure=String(error);r.error=failure;}
 finally{
  try{exposure.setValue(oldValue);exposure.setAuto(oldAuto);r.restoredExposure=Number(exposure.getValue());r.restoredAuto=exposure.isAuto();r.exposureRestored=r.restoredExposure===oldValue&&r.restoredAuto===oldAuto;if(!r.exposureRestored)throw Error('Original exposure not restored exactly');}
  catch(restoreError){r.restoreError=String(restoreError);failure=failure||r.restoreError;}
  try{gate();r.afterSnapshot=snapshot();r.liveConfigurationAfterSha256=configHash();r.configurationRestored=r.liveConfigurationAfterSha256===beforeHash;if(!r.configurationRestored)throw Error('Live configuration differs after exposure restore');}
  catch(finalError){r.finalError=String(finalError);failure=failure||r.finalError;}
  r.finishedAt=new Date().toISOString();r.status=failure?'failed-inspect-restoration':'completed-exposure-bracket-restored-awaiting-image-review';save();print(String(out));
 }
 if(failure)throw Error(failure);
})();
