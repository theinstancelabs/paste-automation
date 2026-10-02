import javax.script.*;
import java.nio.file.*;

/** Executes the exact immutable evidence cache/readers from the native script in Nashorn. */
public final class EvaluatePreflightEvidenceCache {
    private static String between(String source, String start, String end) {
        int a = source.indexOf(start), b = source.indexOf(end, a);
        if (a < 0 || b < 0) throw new IllegalStateException("Native cache/readers markers missing");
        return source.substring(a, b);
    }

    public static void main(String[] args) throws Exception {
        ScriptEngine engine = new ScriptEngineManager().getEngineByName("nashorn");
        if (engine == null) throw new IllegalStateException("Installed Nashorn unavailable");
        String source = Files.readString(Path.of(args[0]));
        String cache = between(source, " function freeze(value)", " var q=JSON.parse");
        String readers = between(source, " function boundJson(e)", " var manualHomeLedgerContinuity=")
                + between(source, " function ftpEvidence(e,json)", " var applicationRestartContext=");
        engine.eval("var F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8,MD=Java.type('java.security.MessageDigest');"
                + "var hashCalls=0;function hash(bytes){hashCalls++;var a=MD.getInstance('SHA-256').digest(bytes),s='';for(var i=0;i<a.length;i++)s+=('0'+((a[i]&255).toString(16))).slice(-2);return s;}");
        engine.eval(cache);
        engine.eval(readers);
        Object result = engine.eval(
                "var freezeCalls=0,realFreeze=freeze;freeze=function(v){freezeCalls++;return realFreeze(v);};"
                + "var parseCalls=0,realParse=JSON.parse;JSON.parse=function(s){parseCalls++;return realParse(s);};"
                + "var file=F.createTempFile('preflight-evidence-cache-','.json');"
                + "Fs.write(file.toPath(),new java.lang.String('{\\\"outer\\\":{\\\"value\\\":7}}').getBytes(UTF));"
                + "var ref={path:String(file.getCanonicalPath()),sha256:hash(Fs.readAllBytes(file.toPath()))};hashCalls=0;"
                + "var first=boundJson(ref),freezesAfterFirst=freezeCalls,parsesAfterFirst=parseCalls,second=manualHomeRead(ref,true),third=ftpEvidence(ref,true);"
                + "if(first!==second||first!==third)throw Error('cached readers did not reuse the same JSON object');"
                + "if(hashCalls!==3)throw Error('every reader must recheck SHA-256, got '+hashCalls);"
                + "if(parseCalls!==parsesAfterFirst||freezeCalls!==freezesAfterFirst||parseCalls!==1||freezeCalls===0)throw Error('cache must parse/freeze each unique JSON exactly once; parses='+parseCalls+' freezes='+freezeCalls);"
                + "if(!Object.isFrozen(first)||!Object.isFrozen(first.outer))throw Error('cached object is not deeply frozen');"
                + "Fs.write(file.toPath(),new java.lang.String('{\\\"outer\\\":{\\\"value\\\":8}}').getBytes(UTF));"
                + "var rejected=false;try{boundJson(ref);}catch(e){rejected=true;}if(!rejected)throw Error('modified evidence accepted on cache hit');"
                + "file.delete();'Nashorn cache passed: repeated hash, immutable reuse, and changed-file rejection'");
        System.out.println(result);
    }
}
