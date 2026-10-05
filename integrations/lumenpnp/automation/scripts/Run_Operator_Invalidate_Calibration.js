// Reviewed no-motion invalidation after a board replacement; calibration sidecar only.
(function(){
 var J=Java.type,S=J('javax.swing.SwingUtilities'),api=null,profileId=null;
 function find(){
  for each(var w in J('java.awt.Window').getWindows())if(w.isVisible()&&w instanceof J('javax.swing.JFrame')&&String(w.getTitle()).indexOf('Paste experiments')===0){
   if(api)throw Error('Multiple paste consoles');
   api=w.getRootPane().getClientProperty('pasteOperatorApi');
   profileId=String(w.getRootPane().getClientProperty('pasteOperatorProfileId'));
  }
 }
 if(S.isEventDispatchThread())find();else S.invokeAndWait(new (J('java.lang.Runnable'))({run:find}));
 if(!api||typeof api.status!=='function'||typeof api.disarm!=='function'||typeof api.invalidateCalibration!=='function'||typeof api.calibrationStatus!=='function')throw Error('Open the current paste console with calibration invalidation support');
 var s=api.status();
 if(s.error||s.busy!==false||s.latched!==false||s.jobState!=='Stopped')throw Error('Healthy idle console and stopped job required for calibration invalidation');
 var c=api.calibrationStatus(),F=J('java.io.File'),Fs=J('java.nio.file.Files'),MD=J('java.security.MessageDigest'),UTF=J('java.nio.charset.StandardCharsets').UTF_8;
 if(!c||typeof c.path!=='string'||profileId==='null'||!profileId)throw Error('Current calibration sidecar/profile identity unavailable');
 var sidecar=new F(c.path),canonical=sidecar.getCanonicalPath(),runs=new F('/home/lumen/lumenpnp/automation/evidence/operator-paste-runs').getCanonicalPath();
 if(!sidecar.isFile()||canonical.indexOf(runs+F.separator)!==0||sidecar.getName()!=='calibration-'+profileId+'.json')throw Error('Exact current calibration sidecar must exist before backup');
 function hash(data){var d=MD.getInstance('SHA-256').digest(data),v='';for(var i=0;i<d.length;i++)v+=('0'+((d[i]&255).toString(16))).slice(-2);return v;}
 var original=Fs.readAllBytes(sidecar.toPath()),before=JSON.parse(String(new java.lang.String(original,UTF))),sha=hash(original),profileFile=new F('/home/lumen/lumenpnp/automation/plans/paste-operator-profile.json'),ledgerFile=new F('/home/lumen/lumenpnp/automation/evidence/operator-paste-runs/'+before.sessionId+'/budget-ledger.json');
 if(!profileFile.isFile()||!ledgerFile.isFile())throw Error('Current profile and ledger must be present for no-change verification');
 var profileBytes=Fs.readAllBytes(profileFile.toPath()),ledgerBytes=Fs.readAllBytes(ledgerFile.toPath());
 if(JSON.parse(String(new java.lang.String(profileBytes,UTF))).id!==profileId||JSON.parse(String(new java.lang.String(profileBytes,UTF))).sessionId!==before.sessionId)throw Error('Profile does not match current calibration identity');
 var profileSha=hash(profileBytes),ledgerSha=hash(ledgerBytes),backupRoot=new F('/home/lumen/lumenpnp/.local-machine-backups'),dir=new F(backupRoot,'operator-calibration-invalidation-'+String(J('java.util.UUID').randomUUID()));
 if(!backupRoot.isDirectory()||!dir.mkdir())throw Error('Could not create exclusive private calibration backup directory');
 var backup=new F(dir,'calibration-before.json');Fs.write(backup.toPath(),original);
 if(hash(Fs.readAllBytes(backup.toPath()))!==sha)throw Error('Calibration backup verification failed; no invalidation performed');
 // These API calls only disarm and clear in-memory/saved calibration references.
 api.disarm();api.invalidateCalibration();
 var after=api.calibrationStatus(),saved=JSON.parse(String(new java.lang.String(Fs.readAllBytes(sidecar.toPath()),UTF)));
 if(after.alignmentApplied!==false||after.zApplied!==false||after.ready!==false||after.lastApproach!==null||saved.alignmentApplied!==false||saved.zApplied!==false||saved.alignmentSamples.length!==0||saved.zSamples.length!==0||saved.ztouchSamples.length!==0||hash(Fs.readAllBytes(profileFile.toPath()))!==profileSha||hash(Fs.readAllBytes(ledgerFile.toPath()))!==ledgerSha)throw Error('Calibration invalidation or profile/ledger preservation did not verify cleanly');
 var review={schema:1,scope:'operator-board-replacement-calibration-invalidation',profileId:profileId,sessionId:before.sessionId,sidecarPath:sidecar.getCanonicalPath(),backupPath:backup.getCanonicalPath(),backupSha256:sha,profileSha256Unchanged:profileSha,ledgerSha256Unchanged:ledgerSha,afterCalibration:after,noMachineMotion:true,profileOrLedgerChanged:false,completedAt:new Date().toISOString()};
 var out=new F(dir,'review.json');Fs.write(out.toPath(),new java.lang.String(JSON.stringify(review,null,2)+'\n').getBytes(UTF));
 print(JSON.stringify({status:'calibration-invalidated',backup:backup.getCanonicalPath(),backupSha256:sha,review:out.getCanonicalPath(),noMachineMotion:true,profileOrLedgerChanged:false}));
})();
