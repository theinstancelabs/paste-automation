import hashlib, importlib.util, json, tempfile, unittest
from pathlib import Path

MODULE=Path(__file__).with_name('author-manual-home-ledger-continuation.py')
SPEC=importlib.util.spec_from_file_location('manual_continuation_author',MODULE)
A=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(A)

class ContinuationAuthorTests(unittest.TestCase):
 def test_reconstructs_original_prefix_before_first_of_two_wet_runs(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td)
   def write(name,obj):
    p=d/name;p.write_text(json.dumps(obj,indent=2)+'\n');return p
   baseline_ledger={'schema':1,'sessionId':'s','syringeId':'sy','status':'verified','entries':[],'lastVerifiedB':-10,'totalAbsoluteDegrees':0}
   old=write('old-ledger.json',baseline_ledger); old_ref=A.evidence(old)
   barrier_old=write('old-barrier.json',{'status':'completed-read-only-position-barrier','noMotionCommandSubmitted':True})
   baseline=write('baseline.json',{'schema':1,'scope':'manual-home-ledger-anchor-continuity','sessionId':'s','syringeId':'sy','currentLedgerEvidence':old_ref,'currentBarrierEvidence':A.evidence(barrier_old),'historicalAnchorReports':[]})
   base_ref=A.evidence(baseline); old_barrier_ref=A.evidence(barrier_old)
   def wet(name,previous_hash,previous_ref,start,end,index):
    ledger_obj=json.loads(old.read_text()) if index==1 else previous
    entries=list(ledger_obj['entries'])+[{'batchId':name,'absoluteDegrees':abs(end-start),'status':'verified'}]
    current=dict(ledger_obj);current['entries']=entries;current['lastVerifiedB']=end;current['totalAbsoluteDegrees']=sum(e['absoluteDegrees'] for e in entries)
    lp=write(name+'-ledger.json',current);lr=A.evidence(lp)
    req={'id':name,'mode':'wet','manualHomeLedgerAnchorEvidence':base_ref if index==1 else {'path':'/prior-continuation.json','sha256':'a'*64},
      'barrierEvidence':old_barrier_ref if index==1 else {'path':'/fresh-barrier.json','sha256':'b'*64},'expectedRaw':{'B':start},
      'previousLedgerSha256':previous_hash,'jvmStartMs':123,'liveConfigurationSha256':'c'*64}
    report={'id':name,'request':req,'status':'completed-contiguous-batch-awaiting-observation','uncertainCompletion':False,
      'completedLedgerSha256':lr['sha256'],'after':{'reported':{'B':end},'counts':{'B':A.controller_step_count(end)}}}
    rp=write(name+'-report.json',report)
    if index==1:return rp,lp,current,lr
    return rp,lp,current,lr
   r1,l1,previous,lr1=wet('wet1',old_ref['sha256'],None,-10,-20,1)
   r2,l2,final,lr2=wet('wet2',lr1['sha256'],A.evidence(r1),-20,-35,2)
   # The second report's terminal barrier is a fresh current-JVM read-only barrier.
   barrier=write('current-barrier.json',{'status':'completed-read-only-position-barrier','noMotionCommandSubmitted':True})
   out=d/'continuation.json'
   args=type('Args',(),{'baseline_proof':str(baseline),'first_wet_report':str(r1),'ledger_snapshot':str(l1),
      'wet_pair':[str(r2)+'::'+str(l2)],'current_barrier':str(barrier),'output':str(out),'latest_terminal_report':None})()
   A.build(args); result=json.loads(out.read_text())
   self.assertEqual(len(result['continuationEvidence']['verifiedBMotionReports']),2)
   self.assertEqual(result['continuationEvidence']['reconstructedBaseLedger']['sha256'],old_ref['sha256'])
   self.assertEqual(result['currentLedgerEvidence']['sha256'],lr2['sha256'])

 def test_report_rounding_tolerance_keeps_controller_count_binding(self):
  self.assertTrue(A.same_report_b(-4081.8999999999996,-4081.9))
  self.assertEqual(A.controller_step_count(-4081.8999999999996),-18124)
  self.assertFalse(A.same_report_b(-4081.899,-4081.9))

if __name__=='__main__': unittest.main()
