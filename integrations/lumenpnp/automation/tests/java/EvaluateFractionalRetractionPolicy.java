import javax.script.*;
import java.nio.file.*;

/** Runs the pure comparison policy in installed Nashorn; no machine APIs are loaded. */
public final class EvaluateFractionalRetractionPolicy {
    public static void main(String[] args) throws Exception {
        ScriptEngine engine = new ScriptEngineManager().getEngineByName("nashorn");
        if (engine == null) throw new IllegalStateException("Installed Nashorn unavailable");
        engine.eval(Files.readString(Path.of(args[0])));
        engine.eval(Files.readString(Path.of(args[1])));
        engine.eval(Files.readString(Path.of(args[2])));
        System.out.println(engine.eval("JSON.stringify(FractionalRetractionTraces)"));
    }
}
