// Model-only restoration of the N2 exclusion field initialized by OpenPnP startup.
(function(){
var C=Java.type('org.openpnp.model.Configuration'),F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8,MD=Java.type('java.security.MessageDigest'),L=Java.type('org.openpnp.model.Location'),MM=Java.type('org.openpnp.model.LengthUnit').Millimeters;
var m=C.get().getMachine(),n=m.getDefaultHead().getNozzleByName('N2');
function bytes(s){return new java.lang.String(s).getBytes(UTF);}function hash(b){var a=MD.getInstance('SHA-256').digest(b),s='';for(var i=0;i<a.length;i++)s+=('0'+((a[i]&255).toString(16))).slice(-2);return s;}
function xml(){var w=new java.io.StringWriter();C.createSerializer().write(m,w);return String(w);}
var before=xml();if(hash(bytes(before))!=='2146de0b0767aa7f7c52325cedde40aed4206364464f237adea363392a3463cd'||Number(Java.type('java.lang.management.ManagementFactory').getRuntimeMXBean().getStartTime())!==1790804279580)throw Error('Exact inspected startup state required');
if(m.isBusy()||m.isHomed()||!m.isEnabled()||m.getDrivers().size()!==1||m.getDrivers().get(0).isMotionPending()||n.getNozzleTip()!=null||n.getCompatibleNozzleTips().size()!==0||n.isChangerEnabled()||n.getRotationModeOffset()!=null||m.getPnpJobProcessor().isPreRotateAllNozzles())throw Error('Idle unhomed startup with otherwise quarantined N2 required');
var out=new F('/home/lumen/lumenpnp/.local-machine-backups/paste-startup-quarantine-'+java.lang.System.currentTimeMillis());if(!out.mkdir())throw Error('Unique backup required');var disk=new F(C.get().getConfigurationDirectory(),'machine.xml'),diskBytes=Fs.readAllBytes(disk.toPath());Fs.write(new F(out,'disk-before.xml').toPath(),diskBytes);Fs.write(new F(out,'live-before.xml').toPath(),bytes(before));
n.setManualNozzleTipChangeLocation(new L(MM,0,0,0,0));
if(n.getManualNozzleTipChangeLocation().isInitialized()||hash(Fs.readAllBytes(disk.toPath()))!==hash(diskBytes))throw Error('Quarantine verification failed');
var after=xml();Fs.write(new F(out,'live-after.xml').toPath(),bytes(after));Fs.write(new F(out,'report.json').toPath(),bytes(JSON.stringify({status:'startup-N2-manual-change-exclusion-restored',noControllerCommands:true,noMotion:true,configurationSaved:false,liveConfigurationSha256:hash(bytes(after))},null,2)));print(String(out));
})();
