import javax.script.*;import java.nio.file.*;
/** Evaluates pure camera route policy in Nashorn with synthetic stubs only. */
public final class EvaluateFastCameraPolicy {
 public static void main(String[] a)throws Exception{ScriptEngine e=new ScriptEngineManager().getEngineByName("nashorn");if(e==null)throw new IllegalStateException("Nashorn unavailable");e.eval(Files.readString(Path.of(a[0])));e.eval(Files.readString(Path.of(a[1])));System.out.println(String.valueOf(e.eval("FastCameraPolicyCases.run(PasteFastCameraInspection)")));}
}
