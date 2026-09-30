// Installed native formatter, isolated axis/driver/head/machine objects only.
// No connection, serial access or command dispatch; sendGcode is intercepted.
(function(root){
'use strict';
function field(c,n){var f=Java.type(c).class.getDeclaredField(n);f.setAccessible(true);return f;}
function preview(source,command,template){
 var GD=Java.type('org.openpnp.machine.reference.driver.GcodeDriver'),AL=Java.type('org.openpnp.model.AxesLocation'),CT=Java.type('org.openpnp.machine.reference.driver.GcodeDriver$CommandType'),MM=Java.type('org.openpnp.model.LengthUnit').Millimeters;
 var captures=[],rates={};for(var rate=1;rate<=3;rate++)rates[rate]=source.getMinimumRate(rate);
 function forbidden(){throw new java.lang.IllegalStateException('Detached formatter cannot access transport');}
 var Clone=Java.extend(GD,{connect:forbidden,getCommunications:forbidden,getSerial:forbidden,sendCommand:forbidden,
  getMinimumRate:function(order){return rates[Number(order)];},
  getAxisVariables:function(machine){return java.util.Arrays.asList(Java.to(['X','Y','Z','A','B'],'java.lang.String[]'));},
  sendGcode:function(gcode){captures.push(String(gcode));}
 });
 var clone=new Clone();clone.setUnits(source.getUnits());clone.setUsingLetterVariables(source.isUsingLetterVariables());clone.setSupportingPreMove(source.isSupportingPreMove());clone.setMotionControlType(source.getMotionControlType());
 if(String(clone.getUnits())!=='Millimeters'||!clone.isUsingLetterVariables()||clone.isSupportingPreMove())throw Error('Audited letter-variable formatter required');
 clone.setCommand(null,CT.MOVE_TO_COMMAND,template);
 // Copy immutable scalar cache values, never share mutable SendOnChange holders.
 ['sendOnChangeFeedRate','sendOnChangeAcceleration','sendOnChangeJerk'].forEach(function(name){var f=field('org.openpnp.machine.reference.driver.GcodeDriver',name),original=f.get(source);if(original===null){f.set(clone,null);return;}var klass=Java.type('org.openpnp.machine.reference.driver.GcodeDriver$SendOnChange').class,ctor=klass.getDeclaredConstructor();ctor.setAccessible(true);var copy=ctor.newInstance();['sendOnChange','relativeDeviation','variable','lastValue'].forEach(function(key){var part=field('org.openpnp.machine.reference.driver.GcodeDriver$SendOnChange',key);part.set(copy,part.get(original));});f.set(clone,copy);});
 var machine=new (Java.type('org.openpnp.machine.reference.ReferenceMachine'))(),head=new (Java.type('org.openpnp.machine.reference.ReferenceHead'))(),mountable=new (Java.type('org.openpnp.machine.reference.ReferenceNozzle'))();machine.addHead(head);head.addNozzle(mountable);
 var start=new AL(),end=new AL(),moved=new AL(),copies=[];
 for each(var originalAxis in command.getLocation1().getControllerAxes()){
  var axis=new (Java.type('org.openpnp.machine.reference.axis.ReferenceControllerAxis'))();axis.setType(originalAxis.getType());axis.setLetter(originalAxis.getLetter());axis.setDriver(clone);axis.setInvertLinearRotational(originalAxis.isInvertLinearRotational());axis.setDriverCoordinate(originalAxis.getDriverCoordinate());machine.addAxis(axis);copies.push(axis);
  start=start.put(new AL(axis,command.getLocation0().getCoordinate(originalAxis)));end=end.put(new AL(axis,command.getLocation1().getCoordinate(originalAxis)));
  if(command.getMovedAxesLocation().contains(originalAxis))moved=moved.put(new AL(axis,command.getMovedAxesLocation().getCoordinate(originalAxis)));
 }
 var MC=Java.type('org.openpnp.model.Motion$MoveToCommand'),detached=new MC(null,start,end,moved,command.getFeedRatePerSecond(),command.getAccelerationPerSecond2(),command.getJerkPerSecond3(),command.getTimeStart(),command.getTimeDuration(),command.getV0(),command.getV1());
 clone.moveTo(mountable,detached);
 if(captures.length!==1)throw Error('Expected one intercepted native formatter call');
 var lines=captures[0].split(/\r?\n/).map(function(line){return line.trim().replace(/\s+/g,' ');}).filter(function(line){return line.length;});
 return {scope:'disconnected-native-GcodeDriver-moveTo-formatter',transportCalls:0,expandedCommands:lines,rawExpandedText:captures[0],minimumRates:[Number(rates[1].convertToUnits(MM).getValue()),Number(rates[2].convertToUnits(MM).getValue()),Number(rates[3].convertToUnits(MM).getValue())],sendOnChangeCacheCopied:true,allMutableMotionObjectsDetached:true};
}
root.PasteWastePrimeNativePreview={preview:preview};
})(this);
