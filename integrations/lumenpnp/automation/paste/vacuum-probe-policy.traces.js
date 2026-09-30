// Pure ES5 synthetic traces shared by Node and installed Nashorn tests.
// No machine/profile values, Java access, timers, IO or actuation.
(function(root){
 var p=root.VacuumProbePolicy,results=[];
 function config(direction){return {responseDirection:direction,startZmm:8,minZmm:7,stepMm:0.2,maxDescentMm:1,baselineSamples:4,baselineTolerance:0.5,noiseFloor:1,candidateMinDelta:3,samplesToConfirm:2,sampleIntervalMinMs:10,sampleIntervalMaxMs:200,maxDurationMs:5000};}
 function trace(name,direction,ops,patch){var c=config(direction);Object.keys(patch||{}).forEach(function(k){c[k]=patch[k];});var s=p.createProbe(c,0),records=[];ops.forEach(function(op){var r=op[0]==='sample'?p.sample(s,op[1],op[2]):p.acknowledgeZMove(s,op[1],op[2]);records.push(JSON.parse(JSON.stringify(r)));});results.push({name:name,records:records});}
 var base=[['sample',100,0],['sample',100,20],['sample',100,40],['sample',100,60],['ack',7.8,80]];
 trace('seal-decrease','decrease',base.concat([['sample',95,100],['sample',95,120],['sample',90,140]]));
 trace('seal-increase','increase',base.concat([['sample',105,100],['sample',105,120]]));
 trace('opposite-decrease','decrease',base.concat([['sample',102,100],['sample',100,120]]));
 trace('opposite-increase','increase',base.concat([['sample',98,100],['sample',100,120]]));
 trace('partial','decrease',base.concat([['sample',98.5,100],['sample',98.6,120]]));
 trace('disappearing','decrease',base.concat([['sample',98,100],['sample',100,120]]));
 trace('opposite-during-confirmation','decrease',base.concat([['sample',98,100],['sample',102,120]]));
 trace('unstable','decrease',[['sample',100,0],['sample',100,20],['sample',100,40],['sample',102,60]]);
 trace('sample-before-ack','decrease',base.slice(0,4).concat([['sample',100,80]]));
 trace('wrong-ack','decrease',base.slice(0,4).concat([['ack',7.7,80]]));
 trace('too-fast','decrease',base.concat([['sample',100,81]]));
 trace('too-late','decrease',base.concat([['sample',100,500]]));
 trace('nan-reading','decrease',base.concat([['sample',NaN,100]]));
 trace('nonnumber-reading','decrease',base.concat([['sample','100',100]]));
 trace('deadline','decrease',base.concat([['sample',100,6000]]));
 var floor=base.slice(0),t=100;
 for(var i=0;i<5;i++){floor.push(['sample',100,t],['sample',100,t+20]);t+=40;if(i<4){floor.push(['ack',Math.round((7.6-i*0.2)*1e9)/1e9,t]);t+=20;}}
 trace('bounded-floor','decrease',floor);
 results.push({name:'repeatability',result:p.evaluateContactRepeatability([5,5.04,4.98],0.1,3)});
 results.push({name:'repeatability-reject',result:p.evaluateContactRepeatability([5,NaN,5],0.1,3)});
 root.VacuumProbeTraces=results;
})(this);
