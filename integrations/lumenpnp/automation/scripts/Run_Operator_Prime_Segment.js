// Consume one fresh, profile/B-bound initial syringe-prime request through the existing native owner.
(function(){
 var J=Java.type,S=J('javax.swing.SwingUtilities'),F=J('java.io.File'),Files=J('java.nio.file.Files'),Copy=J('java.nio.file.StandardCopyOption'),UTF=J('java.nio.charset.StandardCharsets').UTF_8;
 var root=String(java.lang.System.getenv('LUMEN_AUTOMATION_ROOT')||(java.lang.System.getProperty('user.home')+'/lumenpnp'))+'/',api=null,profileId=null;
 function find(){for each(var w in J('java.awt.Window').getWindows())if(w.isVisible()&&w instanceof J('javax.swing.JFrame')&&String(w.getTitle()).indexOf('Paste experiments')===0){if(api)throw Error('Multiple paste consoles');api=w.getRootPane().getClientProperty('pasteOperatorApi');profileId=String(w.getRootPane().getClientProperty('pasteOperatorProfileId'));}}
 if(S.isEventDispatchThread())find();else S.invokeAndWait(new (J('java.lang.Runnable'))({run:find}));
 if(!api||typeof api.primeSegment!=='function')throw Error('Reload the reviewed console with bounded prime-segment support');
 var status=api.status();if(status.error||status.busy!==false||status.latched!==false||status.homed!==true||status.enabled!==true||status.connected!==true||status.jobState!=='Stopped')throw Error('Idle, healthy, homed, enabled console with stopped job required');
 var path=root+'automation/plans/operator-prime-segment-request.json',file=new F(path);if(!file.isFile())throw Error('Fresh operator-prime-segment request file required');
 var q=JSON.parse(String(new java.lang.String(Files.readAllBytes(file.toPath()),UTF)));if(q.profileId!==profileId||!status.raw||q.currentB!==status.raw.B)throw Error('Prime request profile/current B differs from current console');
 if(q.scope!=='operator-prime-segment'||typeof q.degrees!=='number'||!isFinite(q.degrees)||q.degrees<1||q.degrees>30||Math.floor(q.degrees)!==q.degrees||typeof q.speedDegreesPerSecond!=='number'||!isFinite(q.speedDegreesPerSecond)||q.speedDegreesPerSecond<5||q.speedDegreesPerSecond>20)throw Error('Prime segment must be 1–30 degrees at 5–20 nominal requested B degrees/second');
 // Consume before handoff; a failed request needs a fresh nonce and fresh timestamp, never a replay.
 var consumed=new F(path+'.consumed-'+String(q.nonce));Files.move(file.toPath(),consumed.toPath(),Copy.ATOMIC_MOVE);
 api.primeSegment(q);print('Fresh bounded prime-segment request submitted via the existing native owner: '+q.degrees+' forward B degrees at '+q.speedDegreesPerSecond+' nominal requested B degrees/second; actual rate may differ; no XYZ motion. Inspect output before authorizing another request.');
})();
