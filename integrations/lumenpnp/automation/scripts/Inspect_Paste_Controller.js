// Read-only inspection through the existing OpenPnP owner. Never connects/enables/homes.
(function () {
var C=Java.type('org.openpnp.model.Configuration'), F=Java.type('java.io.File'), Fs=Java.type('java.nio.file.Files');
var m=C.get().getMachine();
if(m.isBusy())throw new Error('Machine busy; inspect after the current operation stops');
var dir=new F('/home/lumen/lumenpnp/automation/evidence/paste-controller-'+java.lang.System.currentTimeMillis());
if(!dir.mkdirs())throw new Error('Cannot create unique evidence folder');
var report={time:new Date().toISOString(),jvmStartMs:Number(Java.type('java.lang.management.ManagementFactory').getRuntimeMXBean().getStartTime()),readOnly:true,enabled:m.isEnabled(),homed:m.isHomed(),drivers:[],nozzles:[],axes:[],preRotateAllNozzles:m.getPnpJobProcessor().isPreRotateAllNozzles(),physicalVerification:false};
function save(){Fs.write(new F(dir,'report.json').toPath(),new java.lang.String(JSON.stringify(report,null,2)).getBytes('UTF-8'));}
for each(var h in m.getHeads())for each(var n in h.getNozzles())report.nozzles.push({id:String(n.getId()),name:String(n.getName()),location:String(n.getLocation()),headOffsets:String(n.getHeadOffsets()),part:n.getPart()==null?null:String(n.getPart().getId()),tip:n.getNozzleTip()==null?null:String(n.getNozzleTip().getName()),changerEnabled:n.isChangerEnabled(),compatibleTipCount:n.getCompatibleNozzleTips().size(),rotationModeOffset:n.getRotationModeOffset()==null?null:Number(n.getRotationModeOffset())});
for each(var a in m.getAxes())report.axes.push({id:String(a.getId()),name:String(a.getName()),type:String(a.getType()),className:String(a.getClass().getName())});
for each(var d in m.getDrivers())report.drivers.push({id:String(d.getId()),name:String(d.getName()),className:String(d.getClass().getName()),cachedFirmware:String(d.getDetectedFirmware()),cachedAxes:String(d.getReportedAxes()),cachedSettings:String(d.getFirmwareConfiguration())});
save();
if(!m.isEnabled()){report.queryStatus='not-queried-machine-disabled';save();print(String(dir));return;}
var U=Java.type('org.openpnp.util.UiUtils'), T=Java.type('org.openpnp.util.UiUtils.Thrunnable');
U.submitUiMachineTask(new T({thrun:function(){
try {
 if(!m.isEnabled())throw new Error('Machine disabled before query');
 var i=0;
 for each(var driver in m.getDrivers()){
  if(String(driver.getClass().getName())!=='org.openpnp.machine.reference.driver.GcodeDriver')throw new Error('Unreviewed driver type');
  var record=report.drivers[i++];record.priorResponses=[];
  var commandType=Java.type('org.openpnp.machine.reference.driver.GcodeDriver$CommandType');
  if(['M114','M114 ; get position'].indexOf(String(driver.getCommand(null,commandType.GET_POSITION_COMMAND)).trim())<0)throw new Error('Unexpected position query command');
  record.beforePositionQuery=[];var beforeAxis={};
  for each(var axis in m.getAxes())if(String(axis.getClass().getName())==='org.openpnp.machine.reference.axis.ReferenceControllerAxis'){
   var saved={id:String(axis.getId()),name:String(axis.getName()),letter:String(axis.getLetter()),modeledDriver:Number(axis.getDriverCoordinate()),modeled:Number(axis.getCoordinate())};
   beforeAxis[saved.id]=saved;record.beforePositionQuery.push(saved);
  }
  save();
  var observed=driver.getReportedLocation(3000);record.reportedLocation=String(observed);record.axisComparison=[];
  for each(var axis in observed.getControllerAxes()){
   var saved=beforeAxis[String(axis.getId())];if(!saved)throw new Error('Unrecorded position axis');
   record.axisComparison.push({id:saved.id,name:saved.name,letter:saved.letter,reported:Number(observed.getCoordinate(axis)),modeledDriverBefore:saved.modeledDriver,modeledBefore:saved.modeled,modeledDriverAfter:Number(axis.getDriverCoordinate()),modeledAfter:Number(axis.getCoordinate())});
  }

  for each(var prior in driver.receiveResponses())record.priorResponses.push(String(prior.getLine()));
  record.queries=[];
  for each(var cmd in ['M115','M503']){
   var q={command:cmd,responses:[]};record.queries.push(q);save();
   driver.sendCommand(cmd,3000);
   for each(var line in driver.receiveResponses())q.responses.push(String(line.getLine()));
   save();
  }
 }
 report.queryStatus='acknowledged-read-only-queries';
} catch(e){report.queryStatus='failed-no-retry';report.error=String(e);}
finally{report.finished=new Date().toISOString();save();print(String(dir));}
}}));
})();
