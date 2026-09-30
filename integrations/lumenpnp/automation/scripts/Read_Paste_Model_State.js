// Pure live-model diagnostic: no controller query, task, actuation or mutation.
(function(){
 var C=Java.type('org.openpnp.model.Configuration'),F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),AL=Java.type('org.openpnp.model.AxesLocation'),MD=Java.type('java.security.MessageDigest'),UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8;
 function field(c,n,o){var f=Java.type(c).class.getDeclaredField(n);f.setAccessible(true);return f.get(o);}
 function hash(b){var a=MD.getInstance('SHA-256').digest(b),s='';for(var i=0;i<a.length;i++)s+=('0'+((a[i]&255).toString(16))).slice(-2);return s;}
 var m=C.get().getMachine(),p=m.getMotionPlanner(),h=m.getDefaultHead(),r={scope:'pure-model-state-no-controller-access',time:new Date().toISOString(),jvmStartMs:Number(Java.type('java.lang.management.ManagementFactory').getRuntimeMXBean().getStartTime()),enabled:m.isEnabled(),homed:m.isHomed(),busy:m.isBusy(),drivers:[],nozzles:[],axes:[],controllerPoseTrusted:false};
 var e=field('org.openpnp.spi.base.AbstractMachine','executor',m),t=field('org.openpnp.spi.base.AbstractMachine','taskThread',m);
 r.executor=e==null?null:{shutdown:e.isShutdown(),terminated:e.isTerminated(),active:Number(e.getActiveCount()),queued:Number(e.getQueue().size())};r.taskOwner=t==null?null:{name:String(t.getName()),alive:t.isAlive()};
 for each(var d in m.getDrivers()){
  var reader=field('org.openpnp.machine.reference.driver.GcodeDriver','readerThread',d),error=field('org.openpnp.machine.reference.driver.GcodeDriver','errorResponse',d);
  r.drivers.push({id:String(d.getId()),connected:!!field('org.openpnp.machine.reference.driver.GcodeDriver','connected',d),readerAlive:reader!=null&&reader.isAlive(),error:error==null?null:String(error),port:String(d.getSerial().getPortName()),motionPending:d.isMotionPending()});
  for each(var a in new AL(m).drivenBy(d).getControllerAxes())r.axes.push({id:String(a.getId()),letter:String(a.getLetter()),model:Number(a.getCoordinate()),driver:Number(a.getDriverCoordinate())});
 }
 for each(var n in h.getNozzles())r.nozzles.push({id:String(n.getId()),name:String(n.getName()),location:String(n.getLocation()),tip:n.getNozzleTip()==null?null:String(n.getNozzleTip().getId()),compatible:Number(n.getCompatibleNozzleTips().size()),changer:n.isChangerEnabled(),part:n.getPart()==null?null:String(n.getPart().getId())});
 r.motionQueue=Number(field('org.openpnp.machine.reference.driver.AbstractMotionPlanner','motionCommands',p).size());r.preRotate=m.getPnpJobProcessor().isPreRotateAllNozzles();
 var w=new java.io.StringWriter();C.createSerializer().write(m,w);r.liveConfigurationSha256=hash(new java.lang.String(String(w)).getBytes(UTF));
 var out=new F('/home/lumen/lumenpnp/automation/evidence/paste-model-state-'+java.lang.System.currentTimeMillis());if(!out.mkdir())throw Error('Unique diagnostic directory required');Fs.write(new F(out,'report.json').toPath(),new java.lang.String(JSON.stringify(r,null,2)+'\n').getBytes(UTF));print(String(out));
})();
