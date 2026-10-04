#!/usr/bin/env python3
"""Preview the experimental conditioned30° recipe; --execute dispatches once."""
import argparse,pathlib,subprocess,sys

def command(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--refs',nargs='+',required=True)
    p.add_argument('--condition-refs',nargs='+',required=True)
    p.add_argument('--root',type=pathlib.Path)
    p.add_argument('--execute',action='store_true')
    p.add_argument('--dose',type=int,choices=[30,40],default=30)
    a=p.parse_args(argv)
    main=[r for token in a.refs for r in token.split(',')]
    cond=[r for token in a.condition_refs for r in token.split(',')]
    if set(main)&set(cond):p.error('Conditioning references must differ from main references')
    cmd=[sys.executable,str(pathlib.Path(__file__).with_name('prepare-operator-experiment.py')),'dispense-and-survey','--refs',*main,'--condition-refs',*cond,'--dose',str(a.dose),'--push-deg-s','50','--retract-percent','10','--retract-deg-s','100','--dwell-ms','1000','--retract-dwell-ms','0','--gap-mm','0.1','--condition-dose','0.25','--retract-each-pad']
    if a.root:cmd.extend(['--root',str(a.root)])
    if a.execute:cmd.append('--execute')
    return cmd

def main(argv=None):
    return subprocess.run(command(argv),check=True)

if __name__=='__main__':main()
