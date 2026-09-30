import java.nio.file.*;
import javax.script.*;
import org.openpnp.machine.reference.driver.GcodeDriver;
import org.openpnp.machine.reference.driver.ReferenceDriverCommunications;

/** Isolated disconnected object only: never loads machine config or opens communications. */
public final class CheckNativeErrorLatch {
    private static final class OfflineDriver extends GcodeDriver {
        @Override public ReferenceDriverCommunications getCommunications() { return getSerial(); }
        void accept(String line) { processResponse(new Line(line)); }
        String fault() { return errorResponse == null ? null : errorResponse.getLine(); }
        void checkFault() throws Exception { bailOnError(); }
        int confirmations() { return receivedConfirmationsQueue.size(); }
        void assertDisconnected() throws Exception {
            java.lang.reflect.Field reader = GcodeDriver.class.getDeclaredField("readerThread");
            reader.setAccessible(true);
            if (connected || reader.get(this) != null || isMotionPending())
                throw new AssertionError("Offline object unexpectedly connected/running");
        }
    }
    public static void main(String[] args) throws Exception {
        ScriptEngine engine = new ScriptEngineManager().getEngineByName("nashorn");
        if (engine == null) throw new IllegalStateException("Installed Nashorn unavailable");
        engine.eval(Files.readString(Path.of(args[0]))); // pure policy only
        String regex = String.valueOf(engine.eval("NativePasteAir.nativeErrorRegex"));
        OfflineDriver driver = new OfflineDriver();
        driver.assertDisconnected();
        driver.setCommand(null, GcodeDriver.CommandType.COMMAND_CONFIRM_REGEX, "^ok.*");
        java.util.ArrayList<GcodeDriver.Command> previous = driver.commands;
        java.util.ArrayList<GcodeDriver.Command> replacement = new java.util.ArrayList<>(previous);
        replacement.add(new GcodeDriver.Command(null, GcodeDriver.CommandType.COMMAND_ERROR_REGEX, regex));
        driver.commands = replacement;
        if (previous.size() != 1 || replacement.size() != 2)
            throw new AssertionError("Copy-on-write modified old list");
        for (String line : new String[]{"Error: synthetic", "start", "Resend: 12", "echo:Unknown command"}) {
            driver.accept(line);
            if (!line.equals(driver.fault())) throw new AssertionError("Native parser missed " + line);
            driver.accept("ok");
            if (!line.equals(driver.fault())) throw new AssertionError("ACK erased error");
            try {
                driver.checkFault();
                throw new AssertionError("bailOnError did not throw");
            } catch (Exception expected) {
                if (expected.getMessage() == null || !expected.getMessage().contains(line))
                    throw new AssertionError("Wrong failure: " + expected);
            }
            if (driver.fault() != null) throw new AssertionError("Native cache no longer clears on throw");
        }
        if (driver.confirmations() != 4) throw new AssertionError("ACK path changed");
        driver.commands = previous;
        if (driver.getCommand(null, GcodeDriver.CommandType.COMMAND_ERROR_REGEX) != null)
            throw new AssertionError("Original command list not restored");
        driver.assertDisconnected();
        System.out.println("Offline native parser cached four faults through ACKs; bailOnError threw and cleared each; no communications opened.");
    }
}
