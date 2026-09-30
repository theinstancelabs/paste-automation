import javax.script.*;
import java.nio.file.*;
/** Evaluates only the supplied pure policy and synthetic fixtures; no machine API. */
public final class EvaluatePurePolicy {
    public static void main(String[] args) throws Exception {
        ScriptEngine engine = new ScriptEngineManager().getEngineByName("nashorn");
        if (engine == null) throw new IllegalStateException("Installed Nashorn unavailable");
        engine.eval(Files.readString(Path.of(args[0])));
        engine.eval(Files.readString(Path.of(args[1])));
        System.out.println(engine.eval("JSON.stringify(VacuumProbeTraces)"));
    }
}
