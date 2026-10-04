// Reviewed fixed 5-degree pressure relief at 100 B degrees/second; existing owner only.
(function(){
 var J=Java.type,S=J('javax.swing.SwingUtilities'),api=null;
 function find(){for each(var w in J('java.awt.Window').getWindows())if(w.isVisible()&&w instanceof J('javax.swing.JFrame')&&String(w.getTitle()).indexOf('Paste experiments')===0){if(api)throw Error('Multiple paste consoles');api=w.getRootPane().getClientProperty('pasteOperatorApi');}}
 if(S.isEventDispatchThread())find();else S.invokeAndWait(new (J('java.lang.Runnable'))({run:find}));
 if(!api||typeof api.relievePressure!=='function')throw Error('Reload the console with stationary pressure-relief support');
 var s=api.status();if(s.busy||s.latched||s.error)throw Error('Idle healthy console required');
 api.relievePressure(5,1);print('Stationary +5 B-degree relief submitted at 100 B degrees/second; no XYZ motion. Gross budget and verified pending relief remain recorded by the console.');
})();
