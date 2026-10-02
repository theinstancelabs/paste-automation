#!/usr/bin/env python3
"""Author an offline continuation proof over immutable reports and ledger snapshots.

This tool does not connect to OpenPnP or dispatch any motion. It never edits the
original manual-home proof. Each wet report must have a matching immutable ledger
snapshot whose SHA equals the report's completedLedgerSha256.
"""
import argparse, hashlib, json, math, struct
from pathlib import Path

def evidence(path):
    p=Path(path).resolve(strict=True); data=p.read_bytes()
    if not data: raise ValueError(f'empty evidence: {p}')
    return {'path':str(p),'sha256':hashlib.sha256(data).hexdigest()}

def load(ref):
    p=Path(ref['path']); data=p.read_bytes()
    if hashlib.sha256(data).hexdigest()!=ref['sha256']: raise ValueError(f'evidence hash mismatch: {p}')
    return json.loads(data)

def controller_step_count(raw_b):
    """Match the Java controller's float32 B-to-count conversion."""
    f32=lambda value: struct.unpack('<f',struct.pack('<f',float(value)))[0]
    product=f32(f32(raw_b)*f32(4.44))
    return (1 if product >= 0 else -1)*math.floor(abs(product)+0.5)

def same_report_b(raw_b, ledger_b):
    return (isinstance(raw_b,(int,float)) and isinstance(ledger_b,(int,float))
            and math.isfinite(raw_b) and math.isfinite(ledger_b)
            and abs(raw_b-ledger_b)<=1e-7
            and controller_step_count(raw_b)==controller_step_count(ledger_b))

def build(args):
    baseline_ref=evidence(args.baseline_proof); baseline=load(baseline_ref)
    if baseline.get('scope')!='manual-home-ledger-anchor-continuity': raise ValueError('baseline proof must be original manual-home-ledger-anchor-continuity')
    report_ref=evidence(args.first_wet_report); report=load(report_ref); req=report.get('request',{})
    if report.get('status')!='completed-contiguous-batch-awaiting-observation' or req.get('mode')!='wet': raise ValueError('first motion report must be a completed wet batch')
    if req.get('manualHomeLedgerAnchorEvidence')!=baseline_ref: raise ValueError('first wet report must bind the original manual-home proof')
    pairs=[(Path(args.first_wet_report),Path(args.ledger_snapshot))]
    for value in args.wet_pair or []:
        bits=value.split('::',1)
        if len(bits)!=2: raise ValueError('--wet-pair format is REPORT.json::LEDGER-SNAPSHOT.json')
        pairs.append((Path(bits[0]),Path(bits[1])))
    verified=[]; ledger_ref=None; ledger=None
    for idx,(report_path,ledger_path) in enumerate(pairs):
      report_ref=evidence(report_path); report=load(report_ref); req=report.get('request',{})
      if report.get('status')!='completed-contiguous-batch-awaiting-observation' or req.get('mode')!='wet': raise ValueError(f'pair {idx} must be a completed wet batch')
      expected_link=baseline_ref if idx==0 else None
      if idx==0 and req.get('manualHomeLedgerAnchorEvidence')!=expected_link: raise ValueError('first wet report must bind the original manual-home proof')
      ledger_ref=evidence(ledger_path); ledger=load(ledger_ref)
      reported_b=report.get('after',{}).get('reported',{}).get('B')
      reported_count=report.get('after',{}).get('counts',{}).get('B')
      if (report.get('completedLedgerSha256')!=ledger_ref['sha256']
          or not same_report_b(ledger.get('lastVerifiedB'),reported_b)
          or reported_count!=controller_step_count(ledger.get('lastVerifiedB'))):
          raise ValueError(f'pair {idx} ledger hash or final B/count does not match wet report')
      if idx and (req.get('previousLedgerSha256')!=verified[-1]['ledgerEvidence']['sha256'] or not req.get('manualHomeLedgerAnchorEvidence')): raise ValueError(f'pair {idx} does not continue the preceding exact ledger and proof')
      verified.append({'reportEvidence':report_ref,'ledgerEvidence':ledger_ref})
    first_report_ref=verified[0]['reportEvidence']; first_report=load(first_report_ref); first_req=first_report.get('request',{})
    report_ref=verified[-1]['reportEvidence']; report=load(report_ref); req=report.get('request',{})
    barrier_ref=evidence(args.current_barrier); barrier=load(barrier_ref)
    if barrier.get('status')!='completed-read-only-position-barrier' or barrier.get('noMotionCommandSubmitted') is not True: raise ValueError('current barrier must be completed read-only')
    # Recover and byte-verify the original pre-wet accounting anchor from the
    # current ledger prefix. No ledger values are guessed or rewritten.
    cut=next((i for i,e in enumerate(ledger.get('entries',[])) if e.get('batchId')==first_report.get('id')),None)
    if cut is None: raise ValueError('current snapshot lacks the first wet batch ledger suffix')
    reconstructed=dict(ledger); reconstructed['entries']=ledger['entries'][:cut]
    reconstructed['lastVerifiedB']=first_req['expectedRaw']['B']
    reconstructed['totalAbsoluteDegrees']=sum(e['absoluteDegrees'] for e in reconstructed['entries'])
    reconstructed['status']='verified'; reconstructed.pop('activeBatchId',None)
    prefix_bytes=(json.dumps(reconstructed,indent=2,ensure_ascii=False)+'\n').encode()
    prefix_sha=hashlib.sha256(prefix_bytes).hexdigest()
    anchor_ledger=baseline.get('currentLedgerEvidence',{})
    if prefix_sha!=anchor_ledger.get('sha256') or first_req.get('previousLedgerSha256')!=prefix_sha: raise ValueError('reconstructed current-ledger prefix is not byte-identical to the original manual-home ledger')
    if first_req.get('barrierEvidence')!=baseline.get('currentBarrierEvidence'): raise ValueError('first wet report does not continue from original manual-home barrier')
    baseline_req=baseline.get('request',{})
    record={'schema':1,'scope':'manual-home-ledger-anchor-continuation',
      'sessionId':baseline.get('sessionId'),'syringeId':baseline.get('syringeId'),
      'currentJvmStartMs':req.get('jvmStartMs'),'currentConfigurationSha256':req.get('liveConfigurationSha256'),
      'historicalAnchorReports':baseline.get('historicalAnchorReports',[]),
      'continuationEvidence':{'baselineManualHomeProofEvidence':baseline_ref,
        'verifiedBMotionReports':verified,
        'reconstructedBaseLedger':{'sourceLedgerEvidence':ledger_ref,'prefixEntryCount':cut,'sha256':prefix_sha}},
      'currentLedgerEvidence':ledger_ref,'currentBarrierEvidence':barrier_ref,
      'latestTerminalReportEvidence':report_ref}
    if args.latest_terminal_report:
      terminal_ref=evidence(args.latest_terminal_report); terminal_report=load(terminal_ref); tq=terminal_report.get('request',{})
      if (terminal_report.get('status')!='completed-contiguous-air-batch-awaiting-observation'
          or terminal_report.get('uncertainCompletion') is not False
          or terminal_report.get('completedLedgerSha256')!=ledger_ref['sha256']
          or tq.get('mode')!='air' or tq.get('previousLedgerSha256')!=ledger_ref['sha256']
          or tq.get('previousReportEvidence')!=report_ref
          or any(s.get('axis')=='B' for s in tq.get('previewStages',[]))):
          raise ValueError('optional latest terminal must be an exact B-preserving AIR report after the final wet report')
      terminal_b=terminal_report.get('after',{}).get('reported',{}).get('B')
      terminal_count=terminal_report.get('after',{}).get('counts',{}).get('B')
      if (not same_report_b(terminal_b,ledger.get('lastVerifiedB'))
          or terminal_count!=controller_step_count(ledger.get('lastVerifiedB'))):
          raise ValueError('latest AIR report changed the verified final B raw position/count')
      record['latestTerminalReportEvidence']=terminal_ref
    out=Path(args.output).resolve(); out.parent.mkdir(parents=True,exist_ok=True)
    if out in [Path(x).resolve() for x in [args.baseline_proof,args.first_wet_report,args.ledger_snapshot,args.current_barrier]+[p for pair in pairs[1:] for p in pair]]: raise ValueError('output must not overwrite evidence')
    out.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline-proof',required=True);p.add_argument('--first-wet-report',required=True);p.add_argument('--ledger-snapshot',required=True);p.add_argument('--wet-pair',action='append',help='additional REPORT.json::LEDGER-SNAPSHOT.json; repeat in verified ledger order');p.add_argument('--latest-terminal-report',help='optional exact B-preserving AIR report after the last wet report');p.add_argument('--current-barrier',required=True);p.add_argument('--output',required=True)
    a=p.parse_args(); print(build(a))

if __name__=='__main__': main()
