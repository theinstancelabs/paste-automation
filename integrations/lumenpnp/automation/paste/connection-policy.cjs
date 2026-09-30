/* Pure ES5 connection policy, shared by Node tests and installed Nashorn. */
(function(root){
 'use strict';
 var expected=['G21','G90','M260 A112 B1 S1','M260 A109','M260 B48','M260 B27','M260 S1','M260 A112 B2 S1','M260 A109','M260 B48','M260 B27','M260 S1'];
 function fail(message){throw Error(message);}
 function tokens(command){return String(command==null?'':command).split(/\r?\n/).map(function(line){return line.split(';')[0].trim().replace(/\s+/g,' ');}).filter(function(line){return line.length;});}
 function checkCommands(connect,enable,disable){
  var actual=tokens(connect);if(JSON.stringify(actual)!==JSON.stringify(expected))fail('Live connect commands differ from audited G21/G90 and VAC sensor initialization');
  if(tokens(enable).length||tokens(disable).length)fail('Unexpected enable/disable command; connection side effects require new audit');
 }
 function noOwner(exitCode,output){if(exitCode!==1||String(output).trim())fail('Serial device has an owner or ownership probe was inconclusive: '+String(output).trim());}
 function responses(lines){
  lines.forEach(function(line){if(/(?:^|\s)(?:error\s*:|!!|start(?:\s|$)|resend\s*:|rs\s+N?\d)|reset|disconnect/i.test(String(line)))fail('Controller reset/error/resend or disconnect in response: '+line);});
 }
 function checkState(s){
  if(s.enabled!==false||s.homed!==false||s.busy!==false||s.jobState!=='Stopped')fail('Need disabled, unhomed, idle machine and stopped placement job');
  if(s.driverClass!=='org.openpnp.machine.reference.driver.GcodeDriver'||s.driverId!=='DRV16982438146c1dd4'||s.driverCount!==1)fail('Unknown driver topology');
  if(s.connected!==false||s.readerAlive!==false||s.serialOpen!==false)fail('Existing OpenPnP driver/serial owner must be disconnected');
  if(s.serialClass!=='org.openpnp.machine.reference.driver.SerialPortCommunications'||s.communicationsType!=='serial'||s.simulation!==false)fail('Unknown serial communications');
  if(s.baud!==115200||s.flowControl!=='RtsCts'||s.dataBits!=='Eight'||s.stopBits!=='One'||s.parity!=='None'||s.dtr!==false||s.rts!==false||s.lineEnding!=='LF')fail('Serial settings differ from audited configuration');
  if(s.quarantined!==true||s.heldPart!==false)fail('Right-head quarantine and empty nozzles required');
 }
 var api={checkCommands:checkCommands,noOwner:noOwner,checkState:checkState,tokens:tokens,responses:responses};
 if(typeof module!=='undefined')module.exports=api;else root.PasteConnectionPolicy=api;
})(this);
