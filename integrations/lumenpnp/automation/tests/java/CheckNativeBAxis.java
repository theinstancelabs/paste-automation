import org.openpnp.machine.reference.axis.ReferenceControllerAxis;
import org.openpnp.machine.reference.driver.NullMotionPlanner;
import org.openpnp.machine.reference.driver.GcodeDriver;
import org.openpnp.model.*;
import org.openpnp.spi.*;

/** Fresh unconnected mathematical objects only; no Configuration load or machine APIs. */
public final class CheckNativeBAxis {
  // Isolated millimeter system-unit shim; avoids global Configuration access.
  static final class AxisMM extends ReferenceControllerAxis {
    @Override public Length convertToSystem(Length value) { return value.convertToUnits(LengthUnit.Millimeters); }
    @Override public Length convertFromSystem(Length value) { return value.convertToUnits(LengthUnit.Millimeters); }
  }
  static final class Planner extends NullMotionPlanner {
    int limiterCalls;
    AxesLocation checked(AxesLocation target) throws Exception { return limitAxesLocation(null,target,false); }
    @Override public AxesLocation limitRotationAxis(HeadMountable h, AxesLocation t, ReferenceControllerAxis a) {
      limiterCalls++; return t; // Sentinel: actual enabled limiter semantics audited separately in bytecode.
    }
  }
  static void equal(double actual,double expected) {if(Math.abs(actual-expected)>1e-9)throw new AssertionError(actual+" != "+expected);}
  public static void main(String[] args) throws Exception {
    GcodeDriver driver=new GcodeDriver();
    ReferenceControllerAxis b=new AxisMM();b.setType(Axis.Type.Rotation);b.setLetter("B");b.setDriver(driver);
    b.setInvertLinearRotational(true);b.setWrapAroundRotation(false);b.setLimitRotation(true);
    b.setFeedratePerSecond(new Length(50000,LengthUnit.Millimeters));
    b.setAccelerationPerSecond2(new Length(500,LengthUnit.Millimeters));b.setJerkPerSecond3(new Length(2000,LengthUnit.Millimeters));
    b.setCoordinate(720);b.setDriverCoordinate(720);
    Planner planner=new Planner();planner.checked(new AxesLocation(b,719));
    if(planner.limiterCalls!=1)throw new AssertionError("Enabled rotation did not invoke limiter");
    b.setLimitRotation(false);b.setFeedratePerSecond(new Length(100,LengthUnit.Millimeters));
    if(b.isRotationalOnController())throw new AssertionError("Invert flag no longer classifies B as controller-linear");
    AxesLocation saved=new AxesLocation(b,720);
    ReferenceControllerAxis[] fixed=new ReferenceControllerAxis[4];double[] coords={172.16,216.16,26.5,200};
    for(int i=0;i<4;i++) {fixed[i]=new AxisMM();fixed[i].setType(i==3?Axis.Type.Rotation:Axis.Type.values()[i]);fixed[i].setCoordinate(coords[i]);saved=saved.put(new AxesLocation(fixed[i],coords[i]));}
    for(double target:new double[]{719,720,721}) {
      AxesLocation partial=planner.checked(new AxesLocation(b,target));equal(partial.getCoordinate(b),target);
      if(partial.getAxes().size()!=1||planner.limiterCalls!=1)throw new AssertionError("Partial B gained axes or rotation limiter ran");
      AxesLocation merged=saved.put(partial);for(int i=0;i<4;i++){equal(merged.getCoordinate(fixed[i]),coords[i]);equal(fixed[i].getCoordinate(),coords[i]);}
    }
    equal(b.getCoordinate(),720);equal(b.getDriverCoordinate(),720);equal(b.getMotionLimit(1),100);
    Motion motion=new Motion(null,new AxesLocation(b,720),new AxesLocation(b,719),.05,Motion.MotionOption.SpeedOverPrecision);
    equal(motion.getLocation1().getCoordinate(b),719);
    double feed=motion.getFeedRatePerSecond(driver);if(!(feed>0&&feed<=5.000001))throw new AssertionError("Unexpected feed "+feed);
    driver.setMotionControlType(Driver.MotionControlType.ConstantAcceleration);
    Motion installedModeProjection=new Motion(null,new AxesLocation(b,720),new AxesLocation(b,719),.05,Motion.MotionOption.SpeedOverPrecision);
    java.util.List<Motion.MoveToCommand> commands=installedModeProjection.interpolatedMoveToCommands(driver,false);
    if(commands.size()!=1)throw new AssertionError("Direction test projected more than one command");
    Motion.MoveToCommand command=commands.get(0);
    if(command.getMovedAxesLocation().getAxes().size()!=1)throw new AssertionError("Projected command gained other axes");
    equal(command.getMovedAxesLocation().getCoordinate(b),719);
    double projectedFeed=command.getFeedRatePerSecond();
    if(!(projectedFeed>0&&projectedFeed<=5.000001)||!(command.getAccelerationPerSecond2()>0))throw new AssertionError("Invalid projected rate");
    System.out.println("ConstantAcceleration isolated projection: B719 only, feed="+projectedFeed+", acceleration="+command.getAccelerationPerSecond2());
    System.out.println("Offline native partial B719/B720/B721 preserved; XYZ/A unchanged; controller-linear classification; computed feed="+feed+" units/s; no communications opened.");
  }
}
