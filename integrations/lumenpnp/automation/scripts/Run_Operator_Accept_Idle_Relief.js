// Reviewed no-motion acceptance of the current relieved pressure; existing owner only.
(function(){
 var J=Java.type,S=J('javax.swing.SwingUtilities'),api=null;
 function find(){for each(var w in J('java.awt.Window').getWindows())if(w.isVisible()&&w instanceof J('javax.swing.JFrame')&&String(w.getTitle()).indexOf('Paste experiments')===0){if(api)throw Error('Multiple paste consoles');api=w.getRootPane().getClientProperty('pasteOperatorApi');}}
 if(S.isEventDispatchThread())find();else S.invokeAndWait(new (J('java.lang.Runnable'))({run:find}));
 if(!api||typeof api.status!=='function'||typeof api.discardRelief!=='function')throw Error('Reload the current console with idle-relief acceptance support');
 var s=api.status();if(s.error||s.busy!==false||s.latched!==false||s.armed!==true||s.homed!==true||s.enabled!==true||s.connected!==true||s.jobState!=='Stopped')throw Error('Idle, healthy, armed, homed and enabled console with a stopped job required');
 api.discardRelief();print('Operator acceptance of current relieved pressure submitted through the existing API; no commanded pressure or XYZ motion. The console records the decision, clears pending restoration, and preserves gross budget.');
})();
