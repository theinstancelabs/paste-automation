const {test}=require('node:test');
const assert=require('node:assert/strict');
const air=require('./native-air.cjs');
function pose(change={}){return {X:100,Y:200,Z:26.5,A:200,B:720,...change};}
function spec(change={}){return {startRaw:pose(),targets:[pose({X:125,Y:185})],axisOrder:['X','Y'],speedFraction:.05,minimumSpeed:.05,maxSegmentMm:10,...change};}
function context(change={}){return {enabled:true,homed:true,jobStopped:true,emptyHeads:true,quarantined:true,ownedTask:true,plannerEmpty:true,driverNotPending:true,subordinateEmpty:true,completionRegexAbsent:true,minimumSpeed:.05,...change};}
function mock(overrides={}){
 const events=[];let actual=pose();
 const io={events,claim(){events.push(['claim']);},state(){return context();},preflight(path){events.push(['preflight',path.length]);},boundary(start){assert.deepEqual(actual,start);events.push(['boundary']);},record(status,state){events.push(['record',status,JSON.parse(JSON.stringify(state))]);},control(){return null;},move(segment){events.push(['move',segment]);actual={...segment.to};},verify(segment){events.push(['verify',segment]);air.verifyStep(segment.from,actual,segment);},fault(error,state){events.push(['fault',String(error),{...state}]);},...overrides};return io;
}
test('whole path is split into <=10mm one-axis segments, preserving unwrapped B720 and Z/A',()=>{
 const path=air.segments(spec());assert.deepEqual(path.map(s=>s.axis),['X','X','X','Y','Y']);
 for(const s of path){assert.ok(Math.abs(s.to[s.axis]-s.from[s.axis])<=10);assert.deepEqual(Object.keys(s.to).filter(k=>s.to[k]!==s.from[k]),[s.axis]);assert.equal(s.to.B,720);assert.equal(s.to.Z,26.5);assert.equal(s.to.A,200);}
 assert.deepEqual(path.at(-1).to,pose({X:125,Y:185}));assert.equal(path.filter(s=>s.pointComplete).length,1);
 assert.deepEqual(air.segments(spec({axisOrder:['Y','X']})).map(s=>s.axis),['Y','Y','X','X','X']);
});
test('invalid speed clamp requests, target invariants, axes, sizes and excessive counts fail before claim',()=>{
 const bad=[{speedFraction:.01},{speedFraction:.101},{minimumSpeed:.01},{maxSegmentMm:0},{maxSegmentMm:11},{axisOrder:['X','X']},{targets:[]},{targets:Array(10001).fill(pose())},{targets:[pose({B:0})]},{targets:[pose({Z:26.6})]},{targets:[pose({X:NaN})]},{targets:[pose({X:200101})]}];
 for(const edit of bad){const io=mock();assert.throws(()=>air.run(spec(edit),io));assert.deepEqual(io.events,[]);}
});
test('all ownership/pending/clearance prerequisites reject false, including separate subordinate queue',()=>{
 const good=context();air.context(good);
 for(const key of Object.keys(good).filter(k=>k!=='minimumSpeed'))assert.throws(()=>air.context({...good,[key]:false}),new RegExp(key));
 assert.throws(()=>air.context(context({minimumSpeed:.04})));
});
test('claim precedes full-path preflight and every step is verified before next move',()=>{
 const io=mock(),result=air.run(spec(),io);assert.equal(result.finished,true);assert.equal(result.completedSegments,5);assert.equal(result.completedPoints,1);
 assert.deepEqual(io.events.slice(0,3).map(e=>e[0]),['claim','preflight','boundary']);
 assert.deepEqual(io.events.filter(e=>['move','verify'].includes(e[0])).map(e=>e[0]),['move','verify','move','verify','move','verify','move','verify','move','verify']);
 assert.equal(io.events.filter(e=>e[0]==='fault').length,0);
});
test('initial cancel submits no motion; pause after verified segment stops without lift or replay',()=>{
 const initial=mock({control(){return 'cancel';}});const cancelled=air.run(spec(),initial);assert.equal(cancelled.stop,'cancel');assert.equal(initial.events.filter(e=>e[0]==='move').length,0);
 let calls=0;const io=mock({control(){return ++calls===2?'pause':null;}}),result=air.run(spec(),io);
 assert.equal(result.stop,'pause');assert.equal(result.positionVerified,true);assert.equal(result.completedSegments,1);assert.equal(result.completedPoints,0);assert.equal(io.events.filter(e=>e[0]==='move').length,1);
});
test('preflight rejection prevents first move; move/verification faults produce no recovery or next motion',()=>{
 for(const stage of ['preflight','move','verify']){const io=mock();io[stage]=function(){io.events.push([stage]);throw Error('injected '+stage);};assert.throws(()=>air.run(spec(),io),/injected/);assert.equal(io.events.at(-1)[0],'fault');assert.equal(io.events.filter(e=>e[0]==='move').length,stage==='preflight'?0:1);assert.equal(io.events.at(-1)[2].positionVerified,false);}
});
test('loss of ownership between segments prevents every subsequent move',()=>{
 let calls=0;const io=mock({state(){return context({ownedTask:++calls<3});}});assert.throws(()=>air.run(spec(),io),/ownedTask/);assert.equal(io.events.filter(e=>e[0]==='move').length,1);
});
test('firmware evidence rejects changed B, wrong Z/start and wrong delta while permitting report rounding',()=>{
 const s=air.segments(spec())[0];air.verifyStep(s.from,{...s.to,Y:200.001},s);
 for(const after of [{...s.to,B:0},{...s.to,Z:26.53},{...s.to,X:s.to.X+.03}])assert.throws(()=>air.verifyStep(s.from,after,s));
 assert.throws(()=>air.verifyStep({...s.from,X:999},s.to,s));
 assert.throws(()=>air.verifyStep({...s.from,Z:30},{...s.to,Z:30},s));
});
test('duplicate points are recorded without movement and invalid control fails closed',()=>{
 const io=mock(),result=air.run(spec({targets:[pose(),pose()]}),io);assert.equal(result.completedPoints,2);assert.equal(result.completedSegments,0);assert.equal(io.events.filter(e=>e[0]==='move').length,0);
 const invalid=mock({control(){return 'resume';}});assert.throws(()=>air.run(spec(),invalid),/Invalid air control/);assert.equal(invalid.events.filter(e=>e[0]==='move').length,0);
});
test('native session binds full start, fresh image and exact reviewed segmented path',()=>{
 function session(){const p={x:1,y:2,z:3,rotation:4};return {createdMs:1000,nativeExecution:{schema:1,scope:'joint-clearance-single-raw-XY-air',pathClearanceReviewed:true,pathClearanceRecord:'synthetic-only',rawSegmentsSha256:'a'.repeat(64),expectedRaw:pose(),expectedDriver:pose(),expectedNativePoses:{N1:{...p},N2:{...p},top:{...p},bottom:{...p}},clearanceEvidence:{path:'/synthetic-only.jpg',sha256:'b'.repeat(64),capturedMs:900},maxSegmentMm:10}};}
 air.session(session(),1001);
 for(const change of [n=>n.pathClearanceReviewed=false,n=>n.rawSegmentsSha256='bad',n=>delete n.expectedRaw.B,n=>n.expectedDriver.Z=NaN,n=>delete n.expectedNativePoses.bottom,n=>n.clearanceEvidence.capturedMs=-300000,n=>n.clearanceEvidence.capturedMs=1001,n=>n.maxSegmentMm=11]){const s=session();change(s.nativeExecution);assert.throws(()=>air.session(s,1001));}
});
test('failed one-shot claim cannot replay a completed path or enter machine callbacks',()=>{
 let claimed=false;const io=mock({claim(){if(claimed)throw Error('already claimed');claimed=true;}});
 air.run(spec(),io);const before=io.events.length;assert.throws(()=>air.run(spec(),io),/already claimed/);assert.equal(io.events.length,before);
});
