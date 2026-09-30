// One-shot dispatcher for reviewed repository scripts. No automatic looping.
var C=Java.type('org.openpnp.model.Configuration'),F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files');
var requestFile=new F('/home/lumen/lumenpnp/automation/plans/operator-command.json');
var q=JSON.parse(String(new java.lang.String(Fs.readAllBytes(requestFile.toPath()),'UTF-8')));
var actions={'paste-vacuum-baseline':'Record_Paste_Vacuum_Baseline.js','paste-survey-release':'Release_Paste_Survey_Stop.js','paste-survey-audit':'Audit_Paste_Survey_Stop.js','paste-survey':'Survey_Paste_Coupon.js','paste-measure':'Capture_Paste_Measurement.js','paste-connect-inspect':'Connect_Inspect_Paste_Controller.js','paste-quarantine':'Apply_Paste_Quarantine.js','paste-air':'Run_Paste_Air.js','paste-state':'Inspect_Paste_Controller.js',vacuum:'Set_Reviewed_Vacuum_High.js',adopt:'Adopt_Reviewed_Held_Part.js',discover:'Discover_Current_Feeder.js',home:'Home_After_Restart.js',load:'Load_Prepared_FTP_Job.js',register:'Register_Current_FTP.js',recover:'Recover_Retained_Resistor.js',probe:'Probe_Reviewed_XY.js',reconcile:'Reconcile_Removed_R1_R7.js',state:'Inspect_OpenPnP.js',registration:'Check_Fresh_Registration.js',index:'Index_And_Inspect_Pocket.js',opening:'Inspect_Feed_Opening.js',center:'Apply_Reviewed_Pocket_Center.js',pick:'Verify_Reviewed_Pocket_Pick.js',place:'Place_Selected_Resistor.js',record:'Record_Reviewed_Selected.js',review:'Inspect_Board_Components.js',empty:'Inspect_Empty_Baseline.js',seal:'Inspect_Pick_Seal.js'};
if(!actions[q.action]||q.reviewed!==true||Math.abs(java.lang.System.currentTimeMillis()-q.createdMs)>30000||(C.get().getMachine().isBusy()&&['paste-survey-audit','paste-survey-release'].indexOf(q.action)<0))throw new Error('Invalid/stale command or busy machine');
// Installation blocks legacy motion without modifying its calibrated scripts.
if(['paste-vacuum-baseline','paste-survey-release','paste-survey-audit','paste-survey','paste-measure','paste-connect-inspect','paste-state','paste-quarantine','paste-air'].indexOf(q.action)<0){
 var lockFile=new F('/home/lumen/lumenpnp/automation/paste/installation-lock.json'),lock;
 try{lock=JSON.parse(String(new java.lang.String(Fs.readAllBytes(lockFile.toPath()),'UTF-8')));}catch(e){throw new Error('Paste installation lock missing/malformed; legacy reviewed actions blocked');}
 if(!lock||lock.schema!==1||lock.locked!==false)throw new Error('Paste installation locked; legacy reviewed actions blocked until installation and both-head clearance review');
}
Fs.delete(requestFile.toPath());
C.get().getScripting().execute(new F('/home/lumen/lumenpnp/automation/scripts/'+actions[q.action]));
