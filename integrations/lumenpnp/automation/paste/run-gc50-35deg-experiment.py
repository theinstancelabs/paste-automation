#!/usr/bin/env python3
"""Run the saved experimental GC50 cycle on explicitly reviewed, unused pads.

Preview by default. Requires current calibration and a wiped, stationary tip
without a growing bead/strand. Does not home, clean, or reset pressure automatically.
"""
import argparse
import pathlib
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--refs', nargs='+', required=True)
p.add_argument('--condition-refs', nargs='+', required=True)
p.add_argument('--execute', action='store_true')
p.add_argument('--retract-each-pad', action='store_true', help='Retract after every pad; default keeps per-resistor retraction')
a = p.parse_args()
cmd = [sys.executable, str(pathlib.Path(__file__).with_name('prepare-operator-experiment.py')),
       'dispense-and-survey', '--refs', *a.refs, '--condition-refs', *a.condition_refs,
       '--condition-same-cycle', '--dose', '35', '--push-deg-s', '16',
       '--retract-percent', '20', '--retract-deg-s', '100', '--dwell-ms', '2000',
       '--retract-dwell-ms', '500', '--gap-mm', '0.2']
if a.retract_each_pad:
    cmd.append('--retract-each-pad')
if a.execute:
    cmd.append('--execute')
raise SystemExit(subprocess.call(cmd))
