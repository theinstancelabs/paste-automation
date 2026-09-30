/* Pure ES5 request validation shared by Node tests and installed Nashorn. */
(function(root){
'use strict';
function fail(s){throw new Error(s);}
function text(v,label){if(typeof v!=='string'||!v.trim()||v.length>2000)fail(label+' required (maximum 2000 characters)');}
function finite(v,label){if(typeof v!=='number'||!isFinite(v))fail(label+' must be finite');}
function validate(q,now,jvm){
 if(!q||q.schema!==1)fail('Measurement request schema 1 required');
 if(typeof q.id!=='string'||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(q.id))fail('Unique UUID request id required');
 finite(q.createdMs,'createdMs');if(q.createdMs>now||now-q.createdMs>300000)fail('Measurement request expired');
 if(q.jvmStartMs!==jvm)fail('Request belongs to a different OpenPnP session');
 text(q.operator,'operator');
 if(['setup','camera-centered','right-tip-centered','joint-clearance','surface'].indexOf(q.sampleRole)<0)fail('Unsupported sampleRole');
 if(!q.target)fail('Fixed target description required');
 ['id','description','fixture'].forEach(function(k){text(q.target[k],'target '+k);});
 if(q.sampleRole!=='setup'&&q.operatorObservedTarget!==true)fail('Non-setup sample requires operator target observation');
 if(!Array.isArray(q.evidencePaths)||q.evidencePaths.length>20)fail('evidencePaths must be an array of at most 20 existing files');
 q.evidencePaths.forEach(function(p){text(p,'evidence path');if(p.charAt(0)!=='/')fail('Evidence paths must be absolute');});
 if(q.firmwareQueryRecord!==null){text(q.firmwareQueryRecord,'firmware query record');if(q.firmwareQueryRecord.charAt(0)!=='/')fail('Firmware record path must be absolute');}
 if(!Array.isArray(q.physicalMeasurements)||q.physicalMeasurements.length>30)fail('physicalMeasurements must be an array of at most 30 values');
 var names={};q.physicalMeasurements.forEach(function(m){if(!m)fail('Invalid physical measurement');text(m.name,'measurement name');if(names[m.name])fail('Duplicate measurement name');names[m.name]=true;finite(m.value,m.name);if(['mm','degrees','degrees/min','mm/min','mA','ms','count','fraction'].indexOf(m.unit)<0)fail('Explicit supported measurement unit required');text(m.method,'measurement method');});
 if(q.notes!==undefined&&q.notes!=='')text(q.notes,'notes');
 return q;
}
var api={validate:validate};if(typeof module!=='undefined')module.exports=api;else root.PasteMeasurementRequest=api;
})(this);
