import javax.script.*;
import java.nio.file.*;

/** Executes the exact immutable evidence cache/readers from the preview script in Nashorn. */
public final class EvaluatePreviewEvidenceCache {
    private static String between(String source, String start, String end) {
        int a = source.indexOf(start), b = source.indexOf(end, a);
        if (a < 0 || b < 0) throw new IllegalStateException("Preview cache/readers markers missing");
        return source.substring(a, b);
    }

    public static void main(String[] args) throws Exception {
        ScriptEngine engine = new ScriptEngineManager().getEngineByName("nashorn");
        if (engine == null) throw new IllegalStateException("Installed Nashorn unavailable");
        String source = Files.readString(Path.of(args[0]));
        String cache = between(source, " function freezeEvidence(value)", " function boundEvidence(e,json)");
        String boundReader = between(source, " function boundEvidence(e,json)", " if(q.manualHomeLedgerAnchorEvidence)");
        String ftpReader = between(source, " function ftpEvidence(e,json)", " if(PasteFtpTwoPad.isFtp(q))");
        engine.eval("var F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8,MD=Java.type('java.security.MessageDigest');"
                + "var hashCalls=0;function hash(bytes){hashCalls++;var a=MD.getInstance('SHA-256').digest(bytes),s='';for(var i=0;i<a.length;i++)s+=('0'+((a[i]&255).toString(16))).slice(-2);return s;}");
        engine.eval(cache);
        engine.eval(boundReader);
        engine.eval(ftpReader);
        Object result = engine.eval(
                "var freezeCalls=0,realFreeze=freezeEvidence;freezeEvidence=function(v){freezeCalls++;return realFreeze(v);};"
                + "var parseCalls=0,realParse=JSON.parse;JSON.parse=function(s){parseCalls++;return realParse(s);};"
                + "var file=F.createTempFile('preview-evidence-cache-','.json');"
                + "Fs.write(file.toPath(),new java.lang.String('{\\\"outer\\\":{\\\"value\\\":7}}').getBytes(UTF));"
                + "var ref={path:String(file.getCanonicalPath()),sha256:hash(Fs.readAllBytes(file.toPath()))};hashCalls=0;"
                + "var first=boundEvidence(ref,true),freezesAfterFirst=freezeCalls,parsesAfterFirst=parseCalls,second=ftpEvidence(ref,true);"
                + "if(first!==second)throw Error('preview readers did not reuse cached JSON identity');"
                + "if(hashCalls!==2)throw Error('every preview reader must recheck SHA-256, got '+hashCalls);"
                + "if(freezeCalls!==freezesAfterFirst||parseCalls!==parsesAfterFirst||parseCalls!==1||freezeCalls===0)throw Error('preview must parse/freeze each unique JSON once');"
                + "if(!Object.isFrozen(first)||!Object.isFrozen(first.outer))throw Error('cached preview JSON is not deeply frozen');"
                + "Fs.write(file.toPath(),new java.lang.String('{\\\"outer\\\":{\\\"value\\\":8}}').getBytes(UTF));"
                + "var rejected=false;try{boundEvidence(ref,true);}catch(e){rejected=true;}if(!rejected)throw Error('modified evidence accepted on preview cache hit');"
                + "file.delete();'Nashorn preview cache passed: rehash, frozen reuse, changed-file rejection'");
        System.out.println(result);
    }
}
