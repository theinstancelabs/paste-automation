#!/usr/bin/env python3
"""User-watched single-flight priming. External heartbeat and stop file control each pulse."""
import argparse,json,pathlib,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('authorization',type=pathlib.Path)
p.add_argument('previous_report',type=pathlib.Path)
p.add_argument('initial_image',type=pathlib.Path)
p.add_argument('--execute',action='store_true')
a=p.parse_args();auth=json.loads(a.authorization.read_text());stop=pathlib.Path(auth['stopPath']);heartbeat=pathlib.Path(auth['heartbeatPath']);report=a.previous_report.resolve();image=a.initial_image.resolve()
if not a.execute:
 print(json.dumps({'dispatch':False,'singleFlight':True,'degreesPerPulse':300,'maximumCommandedDegrees':auth['maximumCommandedDegrees'],'stopPath':str(stop),'heartbeatPath':str(heartbeat),'maximumHeartbeatAgeSeconds':60}));raise SystemExit
while True:
 if stop.exists() or not heartbeat.exists() or not 0<=time.time()-heartbeat.stat().st_mtime<=60:
  print(json.dumps({'stopped':True,'report':str(report),'reason':'stop requested or external heartbeat expired'}),flush=True);break
 # Parent refreshes heartbeat; this process never renews its own authorization.
 result=subprocess.run(['python3',str(ROOT/'automation/paste/prime-observed-step.py'),str(report),str(image),'--result','user-watching-no-automated-judgment','--degrees','300','--supervised',str(a.authorization.resolve()),'--execute'],cwd=ROOT,capture_output=True,text=True)
 if result.returncode:
  print(result.stdout,flush=True);print(result.stderr,flush=True);raise SystemExit('Stopped on unsuccessful step; no replay. Inspect terminal/evidence before restarting.')
 terminal=json.loads(result.stdout.strip().splitlines()[-1]);report=pathlib.Path(terminal['report']);image=pathlib.Path(terminal['afterImage']);print(json.dumps(terminal),flush=True)
