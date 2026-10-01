#!/usr/bin/env python3
"""Capture 4K stills from the overview camera, restoring its existing preview."""
import argparse,os,signal,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output_directory',type=Path);a=p.parse_args();a.output_directory.mkdir(parents=True,exist_ok=False)
device='/dev/v4l/by-id/usb-Image+_Galyimage_Live_camera_HU123456798765432-video-index0';matches=[]
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:args=[x for x in (proc/'cmdline').read_bytes().decode().split('\0') if x]
 except (OSError,UnicodeError):continue
 if args and args[0]=='gst-launch-1.0' and proc.stat().st_uid==os.getuid():
  used=[x.split('=',1)[1] for x in args if x.startswith('device=')]
  if len(used)==1 and Path(used[0]).resolve(strict=True)==Path(device).resolve(strict=True):matches.append((proc,args))
if len(matches)!=1:raise RuntimeError('Exactly one owned overview preview required')
proc,args=matches[0];env=dict(x.split('=',1) for x in (proc/'environ').read_bytes().decode().split('\0') if '=' in x);fd=os.pidfd_open(int(proc.name));signal.pidfd_send_signal(fd,signal.SIGTERM);os.close(fd);time.sleep(.4)
try:subprocess.run(['gst-launch-1.0','-q','v4l2src','device='+device,'num-buffers=12','!','image/jpeg,width=4000,height=3000,framerate=15/1','!','multifilesink','location='+str(a.output_directory.resolve()/'frame-%02d.jpg')],env=env,check=True,timeout=12,stdout=subprocess.DEVNULL)
finally:
 with open('/tmp/paste-restored-webcam.log','ab') as f:r=subprocess.Popen(args,env=env,stdout=f,stderr=f,start_new_session=True)
 print('restoredPreviewPid='+str(r.pid))
print(a.output_directory/'frame-11.jpg')
