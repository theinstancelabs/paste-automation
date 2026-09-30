import javax.script.ScriptEngine;
import java.nio.file.Files;
import java.nio.file.Path;
import org.openjdk.nashorn.api.scripting.NashornScriptEngineFactory;
/** Offline synthetic fixture only. Does not attach to OpenPnP or load machine XML. */
public final class CheckWastePrimePreview {
    public static void main(String[] args) throws Exception {
        Path root = Path.of(args[0]);
        ScriptEngine engine = new NashornScriptEngineFactory().getScriptEngine();
        engine.eval(Files.readString(root.resolve("automation/paste/waste-prime.cjs")));
        engine.eval(Files.readString(root.resolve("automation/paste/waste-prime-native-preview.js")));
        engine.eval(Files.readString(root.resolve("automation/paste/waste-prime-native-preview.test.js")));
    }
}
