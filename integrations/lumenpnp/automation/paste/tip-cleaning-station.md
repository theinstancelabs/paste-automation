# Registered tip-cleaning station workflow

`prepare-tip-cleaning-station-route.py` reads registered station values from the ignored local file `.local-machine-backups/tip-cleaning-station.json`. The public helper contains no machine coordinates. It previews station moves or a bounded X-only cloth wiggle from a verified source report, hashes a fresh corridor image, and passes the resulting route through `run-survey-route.py`'s commissioning-envelope checks when available. Wiggle requires the source already at the registered cloth Y and recipe wiggle Z; it is limited to 1 mm halfspan and 5 cycles, holds Y/Z/A/B fixed, and returns X to center. It never dispatches motion or changes B.

Example for a reviewed move to the cloth station:

```sh
python3 automation/paste/prepare-tip-cleaning-station-route.py SOURCE_REPORT FRESH_USB_IMAGE cloth \
  --review 'Reviewed whole XY corridor, both heads and fixed B' \
  --write-spec .local-machine-backups/tip-cleaning-route.json
python3 automation/paste/run-survey-route.py .local-machine-backups/tip-cleaning-route.json
```

The second command previews by default. Review its complete route, capture fresh USB camera evidence, and run it with `--execute` only when ready. It stops on expired evidence, a route fault, state drift, or commissioning-envelope mismatch; do not retry an uncertain route.

For a bounded wiggle after the operator has positioned the head at the registered cloth point and explicitly approved the contact height, prepare the route with `cloth-wiggle` instead. The private recipe supplies the halfspan, cycle count, and raw Z; fresh reviewed full-corridor imagery and review text remain required. The planned route returns to center. Inspect fresh final imagery and the tip before deciding whether further action is appropriate.

After the verified route, use `observe-z-step.py` for any explicit vertical approach step, then capture a fresh USB image promptly before the two-step blot cycle through `tip-cleaning-vertical-cycle.py`. Supply the registered cloth raw target and clearance and an explicit dwell. The vertical helper verifies X/Y/A/B stay fixed and never records visual acceptance automatically.

The current acceptance review is exact: a flush, teeny stable trace with no bead or strand. Review the final USB image and tip directly; physical acceptance remains false until an operator records it. Dip and blot need paste pressure relieved beforehand. The private recipe records current registration and taught heights only; those values are not copied into the public integration.
