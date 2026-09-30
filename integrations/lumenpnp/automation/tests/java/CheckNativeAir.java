import javax.script.*;
import java.nio.file.*;
import java.util.regex.Pattern;
/** Pure policy eval and runtime syntax compilation only. No machine class/API use. */
public final class CheckNativeAir {
 public static void main(String[] args) throws Exception {
  ScriptEngine engine = new ScriptEngineManager().getEngineByName("nashorn");
  if (engine == null) throw new IllegalStateException("Installed Nashorn unavailable");
  ((Compilable) engine).compile(Files.readString(Path.of(args[1])));
  engine.eval(Files.readString(Path.of(args[0])));
  Pattern fault = Pattern.compile(String.valueOf(engine.eval("NativePasteAir.nativeErrorRegex")));
  String[] faults={"Error: cold extrusion", "!!", "start", "echo:Reset detected", "disconnect", "Resend: 12", "rs N42", "echo:Unknown command", "Printer halted", "FATAL", "killed"};
  String[] normal={"ok", "ok N5 P15 B3", "X:1.00 Y:2.00 Z:3.00 A:4.00 B:720.00", "echo:busy: processing"};
  for(String line:faults) if(!fault.matcher(line).matches()) throw new AssertionError("Missed fault: "+line);
  for(String line:normal) if(fault.matcher(line).matches()) throw new AssertionError("Rejected normal: "+line);
  System.out.println("runtime compiled without evaluation; native error pattern passed "+(faults.length+normal.length)+" cases");
 }
}
