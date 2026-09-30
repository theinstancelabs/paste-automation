import java.io.File;
import java.lang.instrument.Instrumentation;
import java.nio.file.*;
import javax.swing.SwingUtilities;
/** Local attach bridge: invokes only the fixed, guarded one-shot dispatcher. */
public final class ReviewedCommandAgent {
    public static void agentmain(String ignored, Instrumentation instrumentation) {
        SwingUtilities.invokeLater(() -> {
            try {
                Class<?> c = Class.forName("org.openpnp.model.Configuration");
                Object cfg = c.getMethod("get").invoke(null);
                Object scripting = c.getMethod("getScripting").invoke(cfg);
                scripting.getClass().getMethod("execute", File.class).invoke(scripting,
                    new File("/home/lumen/lumenpnp/automation/scripts/Automation_Reviewed_Command.js"));
            } catch (Throwable e) {
                try { Files.writeString(Path.of("/home/lumen/lumenpnp/automation/plans/bridge-error.txt"), e.toString()+"\n"+String.valueOf(e.getCause())); }
                catch (Exception failed) { failed.printStackTrace(); }
            }
        });
    }
}
