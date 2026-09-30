// Reviewed in-memory, no-motion quarantine for the reserved
// right nozzle N2 before native LumenPnP jobs are allowed to run.
//
// It deliberately does not call move, home, actuate, load/unloadNozzleTip,
// nozzle.calibrate(), machine.enable(), or Configuration.save().
// Run only through the established OpenPnP Java Attach/script dispatcher,
// never by opening a second serial connection. Machine must be disabled/idle.
// All captured state is written under .local-machine-backups for restoration.

var C = Java.type('org.openpnp.model.Configuration');
var F = Java.type('java.io.File');
var Files = Java.type('java.nio.file.Files');
var CopyOption = Java.type('java.nio.file.StandardCopyOption');
var MessageDigest = Java.type('java.security.MessageDigest');
var StandardCharsets = Java.type('java.nio.charset.StandardCharsets');
var Location = Java.type('org.openpnp.model.Location');
var LengthUnit = Java.type('org.openpnp.model.LengthUnit');
var ReferenceNozzle = Java.type('org.openpnp.machine.reference.ReferenceNozzle');
var ReferencePnpJobProcessor = Java.type('org.openpnp.machine.reference.ReferencePnpJobProcessor');

function sha256(file) {
    var digest = MessageDigest.getInstance('SHA-256');
    var bytes = Files.readAllBytes(file.toPath());
    var hash = digest.digest(bytes);
    var out = '';
    for (var i = 0; i < hash.length; i++) {
        var b = hash[i] & 255;
        out += ('0' + b.toString(16)).slice(-2);
    }
    return out;
}
function writeText(file, value) {
    Files.write(file.toPath(), new java.lang.String(value).getBytes(StandardCharsets.UTF_8));
}
function nullableString(value) { return value == null ? null : String(value); }

var cfg = C.get();
var machine = cfg.getMachine();
if (machine == null) throw new Error('No configured OpenPnP machine.');
if (machine.isEnabled()) throw new Error('Refusing quarantine while the machine is enabled. Disable it first.');
if (machine.isBusy()) throw new Error('Refusing quarantine while the machine is busy.');
var panel = Java.type('org.openpnp.gui.MainFrame').get().getJobTab();
var state = panel.getClass().getDeclaredField('state'); state.setAccessible(true);
if (String(state.get(panel)) !== 'Stopped') throw new Error('Placement job must be stopped, not paused.');

var head = machine.getDefaultHead();
if (head == null || String(head.getName()) !== 'H1') {
    throw new Error('Unexpected default head; expected the inspected LumenPnP H1. No changes made.');
}
var n1 = head.getNozzleByName('N1');
var n2 = head.getNozzleByName('N2');
if (n1 == null || n2 == null || !(n2 instanceof ReferenceNozzle)) {
    throw new Error('Expected N1 and reference nozzle N2 on H1. No changes made.');
}
if (n1.getPart() != null || n1.getPartsFeeder() != null || n2.getPart() != null || n2.getPartsFeeder() != null) {
    throw new Error('A nozzle reports a held part or feeder association. Resolve and inspect before quarantine.');
}
if (String(n1.getId()) !== 'N1' || String(n2.getId()) !== 'NOZ1710829fd33a0170' || n2.isChangerEnabled()) throw new Error('Nozzle identity/changer differs from audit; no changes made.');
var jp = machine.getPnpJobProcessor();
if (jp == null || !(jp instanceof ReferencePnpJobProcessor)) {
    throw new Error('Unexpected job processor; cannot safely quarantine native nozzle selection.');
}

var tip = n2.getNozzleTip();
if (tip == null || String(tip.getName()) !== 'N24' || String(tip.getId()) !== 'TIP16f0412ed2d50009') {
    throw new Error('N2 current tip differs from the audited N24 configuration. Review live state; no changes made.');
}
var compatible = [];
var iter = n2.getCompatibleNozzleTips().iterator();
while (iter.hasNext()) {
    var item = iter.next();
    compatible.push({id: String(item.getId()), name: String(item.getName())});
}
var oldRotationOffset = n2.getRotationModeOffset();
var oldManualChangeLocation = n2.getManualNozzleTipChangeLocation();
var oldChangerEnabled = n2.isChangerEnabled();
var oldPreRotate = jp.isPreRotateAllNozzles();
if (oldChangerEnabled) {
    throw new Error('N2 changer is enabled, outside the audited configuration. No changes made.');
}

var configDir = cfg.getConfigurationDirectory();
var diskMachine = new F(configDir, 'machine.xml');
if (!diskMachine.isFile()) throw new Error('machine.xml is missing; no changes made.');
var repo = new F('/home/lumen/lumenpnp');
var backupRoot = new F(repo, '.local-machine-backups');
if (!backupRoot.isDirectory()) throw new Error('Expected private .local-machine-backups directory; no changes made.');
var stamp = String(java.lang.System.currentTimeMillis());
var backup = new F(backupRoot, 'paste-quarantine-' + stamp);
if (!backup.mkdirs()) throw new Error('Could not create quarantine backup directory.');

var diskCopy = new F(backup, 'disk-machine-before.xml');
Files.copy(diskMachine.toPath(), diskCopy.toPath(), CopyOption.REPLACE_EXISTING);
var liveCopy = new F(backup, 'live-machine-before.xml');
var liveWriter = new java.io.StringWriter();
C.createSerializer().write(machine, liveWriter);
writeText(liveCopy, String(liveWriter));
if (!java.util.Arrays.equals(Files.readAllBytes(liveCopy.toPath()), new java.lang.String(String(liveWriter)).getBytes(StandardCharsets.UTF_8))) throw new Error('Live backup verification failed; no changes made.');
var sourceHash = sha256(diskMachine);
var backupHash = sha256(diskCopy);
if (sourceHash !== backupHash) throw new Error('Disk backup hash mismatch; no changes made.');
var manifest = {
    createdAt: new java.util.Date().toInstant().toString(),
    scope: 'in-memory N2 native-use quarantine; machine.xml is not saved',
    openpnpConfigurationDirectory: String(configDir),
    diskMachineSha256: sourceHash,
    diskBackup: String(diskCopy),
    diskBackupSha256: backupHash,
    liveMachineBackup: String(liveCopy),
    liveMachineBackupSha256: sha256(liveCopy),
    head: String(head.getName()),
    n1Id: String(n1.getId()),
    n1TipId: n1.getNozzleTip() == null ? null : String(n1.getNozzleTip().getId()),
    n2Id: String(n2.getId()),
    n2OriginalTip: {id: String(tip.getId()), name: String(tip.getName())},
    n2OriginalCompatibleTips: compatible,
    n2OriginalRotationModeOffset: oldRotationOffset == null ? null : String(oldRotationOffset),
    n2OriginalManualChangeLocation: oldManualChangeLocation == null ? null : String(oldManualChangeLocation),
    n2OriginalChangerEnabled: oldChangerEnabled,
    originalPreRotateAllNozzles: oldPreRotate,
    changes: ['N2 current tip cleared by setNozzleTip(null)', 'N2 compatible nozzle tips removed',
        'N2 rotation mode offset cleared', 'N2 manual nozzle-tip-change location set to undefined (zero)',
        'native preRotateAllNozzles disabled'],
    persistence: 'not explicitly saved; normal OpenPnP exit may persist in-memory state. Reinspect after every restart/restore; do not assume either persistence or restoration.'
};
var manifestFile = new F(backup, 'manifest.json');
writeText(manifestFile, JSON.stringify(manifest, null, 2));

// These audited setters only change OpenPnP model state and send property
// notifications. They do not issue motion or actuator commands.
try {
    n2.setNozzleTip(null);
    for (var i = 0; i < compatible.length; i++) {
        var compatibleTip = machine.getNozzleTip(compatible[i].id);
        if (compatibleTip != null) n2.removeCompatibleNozzleTip(compatibleTip);
    }
    n2.setRotationModeOffset(null);
    n2.setManualNozzleTipChangeLocation(new Location(LengthUnit.Millimeters, 0, 0, 0, 0));
    jp.setPreRotateAllNozzles(false);

    if (n2.getNozzleTip() != null || n2.getCompatibleNozzleTips().size() !== 0 ||
            n2.getRotationModeOffset() != null || n2.isChangerEnabled() ||
            n2.getManualNozzleTipChangeLocation().isInitialized() || jp.isPreRotateAllNozzles() || machine.isEnabled()) {
        throw new Error('Post-change verification failed. Keep machine disabled and restore from backup after review.');
    }
    if (sha256(diskMachine) !== sourceHash) throw new Error('Saved machine.xml changed during quarantine; keep machine disabled and investigate.');
} catch (e) {
    // Roll model-only changes back in memory if any setter/listener fails.
    // Restore by setters only; do not call load/unloadNozzleTip().
    try {
        n2.setNozzleTip(tip);
        var currentTips = [];
        var currentIter = n2.getCompatibleNozzleTips().iterator();
        while (currentIter.hasNext()) currentTips.push(currentIter.next());
        for (var j = 0; j < currentTips.length; j++) n2.removeCompatibleNozzleTip(currentTips[j]);
        for (var k = 0; k < compatible.length; k++) {
            var restoreTip = machine.getNozzleTip(compatible[k].id);
            if (restoreTip != null) n2.addCompatibleNozzleTip(restoreTip);
        }
        n2.setRotationModeOffset(oldRotationOffset);
        n2.setManualNozzleTipChangeLocation(oldManualChangeLocation);
        n2.setChangerEnabled(oldChangerEnabled);
        jp.setPreRotateAllNozzles(oldPreRotate);
        manifest.rollback = 'model-only rollback attempted; verify from a fresh read-only inspection';
    } catch (rollbackError) {
        manifest.rollbackError = String(rollbackError);
    }
    manifest.applyError = String(e);
    writeText(manifestFile, JSON.stringify(manifest, null, 2));
    throw e;
}

manifest.appliedAt = new java.util.Date().toInstant().toString();
manifest.result = 'N2 quarantined in live memory; machine remains disabled; configuration not saved.';
writeText(manifestFile, JSON.stringify(manifest, null, 2));
print('Paste quarantine applied in memory. N2 tip=null, compatibleTips=0, rotationOffset=null, manual tip-change location undefined, preRotateAllNozzles=false. Backup: ' + backup);
