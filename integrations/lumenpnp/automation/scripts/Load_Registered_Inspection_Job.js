// No-motion loader for the disabled registered inspection job. Never saves config.
(function(){
 var C=Java.type('org.openpnp.model.Configuration'),F=Java.type('java.io.File'),Fs=Java.type('java.nio.file.Files'),MD=Java.type('java.security.MessageDigest'),UTF=Java.type('java.nio.charset.StandardCharsets').UTF_8;
 var root='/home/lumen/lumenpnp/',planFile=new F(root+'automation/plans/fast-camera-inspection-request.json');
 function hash(file){var bytes=Fs.readAllBytes(file.toPath()),a=MD.getInstance('SHA-256').digest(bytes),s='';for(var i=0;i<a.length;i++)s+=('0'+((a[i]&255).toString(16))).slice(-2);return s;}
 var q=JSON.parse(String(new java.lang.String(Fs.readAllBytes(planFile.toPath()),UTF)));
 if(q.schema!==1||q.scope!=='camera-only-registered-fast-inspection'||q.enabled!==true||!q.inspectionJob)throw Error('Valid camera inspection request required');
 var jf=new F(q.inspectionJob.jobPath),bf=new F(q.inspectionJob.boardPath);
 if(!jf.isFile()||!bf.isFile()||hash(jf)!==q.inspectionJob.jobSha256||hash(bf)!==q.inspectionJob.boardSha256)throw Error('Hash-bound disabled inspection job changed');
 var cfg=C.get(),machine=cfg.getMachine(),panel=Java.type('org.openpnp.gui.MainFrame').get().getJobTab();
 if(machine.isBusy()||panel.getJob()==null||panel.getJob().getBoardLocations().size()!==0)throw Error('Loader requires idle machine and empty current job');
 // XML is inspected before loading; all placements must remain disabled.
 var factory=Java.type('javax.xml.parsers.DocumentBuilderFactory').newInstance(),doc=factory.newDocumentBuilder().parse(bf);
 var placements=doc.getElementsByTagName('placement');if(placements.getLength()===0)throw Error('Inspection board has no placements');
 for(var i=0;i<placements.getLength();i++)if(String(placements.item(i).getAttributes().getNamedItem('enabled').getNodeValue())!=='false')throw Error('Inspection placement enabled; refusing load');
 var job=cfg.loadJob(jf),Swing=Java.type('javax.swing.SwingUtilities');
 var update=new java.lang.Runnable({run:function(){panel.setJob(job);panel.selectPlacementsHolderLocation(job.getBoardLocations().get(0));panel.refresh();}});if(Swing.isEventDispatchThread())update.run();else Swing.invokeAndWait(update);
 print('Loaded hash-bound disabled inspection job; no config save or motion.');
})();
