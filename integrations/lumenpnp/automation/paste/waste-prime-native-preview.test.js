var C=Java.type('org.openpnp.model.Configuration');C.initialize(new java.io.File('/tmp/openpnp-offline-waste-preview-no-config'));
var GD=Java.type('org.openpnp.machine.reference.driver.GcodeDriver'),AL=Java.type('org.openpnp.model.AxesLocation'),Axis=Java.type('org.openpnp.machine.reference.axis.ReferenceControllerAxis'),Type=Java.type('org.openpnp.spi.Axis$Type'),MM=Java.type('org.openpnp.model.LengthUnit').Millimeters;
var d=new GD();d.setUsingLetterVariables(true);d.setSupportingPreMove(false);d.setUnits(MM);
var a=new Axis();a.setType(Type.Rotation);a.setLetter('B');a.setDriver(d);a.setInvertLinearRotational(true);a.setDriverCoordinate(720);a.setFeedratePerSecond(new (Java.type('org.openpnp.model.Length'))(100,MM));
var fixtureMachine=new (Java.type('org.openpnp.machine.reference.ReferenceMachine'))();fixtureMachine.addAxis(a);C.get().setMachine(fixtureMachine);
var start=new AL(a,720),end=new AL(a,700),MC=Java.type('org.openpnp.model.Motion$MoveToCommand'),command=new MC(null,start,end,end,5.0,1.25,null,null,null,null,null);
var output=PasteWastePrimeNativePreview.preview(d,command,'{Acceleration:M204 S%.0f }\nG1 {X:X%.4f} {Y:Y%.4f} {Z:Z%.4f} {A:A%.4f} {B:B%.4f} {FeedRate:F%.0f}');
print(JSON.stringify(output));if(a.getDriverCoordinate()!==720)throw Error('Fixture source axis changed');if(JSON.stringify(output.expandedCommands)!==JSON.stringify(['M204 S1','G1 B700.0000 F300']))throw Error('Wrong native fixture expansion');
PasteWastePrime.expanded(output.expandedCommands,700);
// The native formatter clamps F against the driver's minimum. Prove the policy
// catches a fixture whose unreviewed rate settings produce F600 despite feed5.
a.setFeedratePerSecond(new (Java.type('org.openpnp.model.Length'))(500,MM));
var fast=PasteWastePrimeNativePreview.preview(d,command,'{Acceleration:M204 S%.0f }\nG1 {X:X%.4f} {Y:Y%.4f} {Z:Z%.4f} {A:A%.4f} {B:B%.4f} {FeedRate:F%.0f}'),rejected=false;
try{PasteWastePrime.expanded(fast.expandedCommands,700);}catch(expected){rejected=true;}if(!rejected)throw Error('Native rate clamp escaped policy');
a.setFeedratePerSecond(new (Java.type('org.openpnp.model.Length'))(100,MM));
// Copy send-on-change cache state rather than silently forcing an extra M204.
d.setSendOnChangeAcceleration(true);var holderField=GD.class.getDeclaredField('sendOnChangeAcceleration');holderField.setAccessible(true);var holder=holderField.get(d),last=holder.getClass().getDeclaredField('lastValue');last.setAccessible(true);last.set(holder,Java.type('java.lang.Double').valueOf(1.25));
var cached=PasteWastePrimeNativePreview.preview(d,command,'{Acceleration:M204 S%.0f }\nG1 {X:X%.4f} {Y:Y%.4f} {Z:Z%.4f} {A:A%.4f} {B:B%.4f} {FeedRate:F%.0f}');
if(JSON.stringify(cached.expandedCommands)!==JSON.stringify(['G1 B700.0000 F300']))throw Error('Send-on-change cache not preserved');
if(a.getDriverCoordinate()!==720||Number(last.get(holder))!==1.25)throw Error('Detached preview mutated source fixture');
print('Offline native formatter checks passed: literal target, native minimum clamp, copied cache and unchanged source axis.');
