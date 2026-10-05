// Restore only the console gap control from the current calibration sidecar; no machine motion.
(function(){
 var J=Java.type,S=J('javax.swing.SwingUtilities'),consoleFrame=null,api=null,changed=null;
 function run(){
  for each(var w in J('java.awt.Window').getWindows())if(w.isVisible()&&w instanceof J('javax.swing.JFrame')&&String(w.getTitle()).indexOf('Paste experiments')===0){
   if(consoleFrame)throw Error('Multiple paste consoles');consoleFrame=w;api=w.getRootPane().getClientProperty('pasteOperatorApi');
  }
  if(!consoleFrame||!api||typeof api.status!=='function'||typeof api.calibrationStatus!=='function')throw Error('Current paste console/API unavailable');
  var s=api.status(),c=api.calibrationStatus();
  if(s.error||s.busy!==false||s.latched!==false||s.jobState!=='Stopped'||J('org.openpnp.model.Configuration').get().getMachine().isBusy())throw Error('Healthy idle console and stopped job required');
  if(!c||c.ready!==true||c.needleTouchRecorded!==true||typeof c.commandedGapMm!=='number'||!isFinite(c.commandedGapMm)||c.commandedGapMm<.10||c.commandedGapMm>1)throw Error('Current calibration has no valid commanded needle-touch gap');
  var gap=null,mode=null,count=0;
  function walk(e){
   if(e instanceof J('javax.swing.JPanel')){var a=e.getComponents();if(a.length>=2&&a[0] instanceof J('javax.swing.JLabel')){var label=String(a[0].getText());
    if(label.indexOf('Commanded gap above needle touch (mm)')===0&&a[1] instanceof J('javax.swing.JSpinner')){gap=a[1];count++;}
    if(label.indexOf('Height mode: gap above touch / raw Z')===0&&a[1] instanceof J('javax.swing.JComboBox'))mode=a[1];
   }}
   if(e instanceof J('java.awt.Container'))for each(var ch in e.getComponents())walk(ch);
  }
  walk(consoleFrame.getContentPane());if(count!==1||!mode)throw Error('Expected exactly one calibrated gap spinner and height mode control');
  gap.setValue(new java.lang.Double(c.commandedGapMm));mode.setSelectedItem('gap');changed={commandedGapMm:c.commandedGapMm,heightMode:String(mode.getSelectedItem()),noMachineMotion:true};
 }
 var task=new (J('java.lang.Runnable'))({run:run});if(S.isEventDispatchThread())task.run();else S.invokeAndWait(task);
 print(JSON.stringify(changed));
})();
