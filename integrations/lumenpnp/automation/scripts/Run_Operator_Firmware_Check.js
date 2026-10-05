// Stationary read-only M503 through the visible console's existing native owner.
(function(){
 var J=Java.type,S=J('javax.swing.SwingUtilities'),api=null;
 function find(){for each(var w in J('java.awt.Window').getWindows())if(w.isVisible()&&w instanceof J('javax.swing.JFrame')&&String(w.getTitle()).indexOf('Paste experiments')===0){if(api)throw Error('Multiple paste consoles');api=w.getRootPane().getClientProperty('pasteOperatorApi');}}
 if(S.isEventDispatchThread())find();else S.invokeAndWait(new (J('java.lang.Runnable'))({run:find}));
 if(!api||typeof api.readFirmwareSettings!=='function')throw Error('Reload the console with stationary firmware-read support');
 var s=api.status();if(s.busy||s.latched||s.error)throw Error('Idle healthy console required');
 api.readFirmwareSettings();print('Stationary firmware read submitted; inspect raw M503, the bare M220 FR percentage report, and before/after M114 evidence. No firmware settings written.');
})();
