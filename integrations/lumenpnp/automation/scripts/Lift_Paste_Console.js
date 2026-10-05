// Request the console's guarded calibration-clearance lift; no extrusion.
(function(){
 var J=Java.type,S=J('javax.swing.SwingUtilities'),api=null;
 function find(){
  for each(var w in J('java.awt.Window').getWindows())
   if(w.isVisible()&&w instanceof J('javax.swing.JFrame')&&String(w.getTitle()).indexOf('Paste experiments')===0){
    if(api)throw Error('Multiple paste consoles');
    api=w.getRootPane().getClientProperty('pasteOperatorApi');
   }
 }
 if(S.isEventDispatchThread())find();else S.invokeAndWait(new (J('java.lang.Runnable'))({run:find}));
 if(!api||typeof api.lift!=='function')throw Error('Reload the console with guarded clearance-lift support');
 var s=api.status();if(s.busy||s.latched||s.error)throw Error('Idle healthy console required');
 api.lift();
 print('Requested guarded calibration-clearance lift through the existing console owner; no paste.');
})();
