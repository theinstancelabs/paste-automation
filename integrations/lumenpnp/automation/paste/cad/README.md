# Cached CAD extraction

Read-only extraction from source FCStd archives. No FreeCAD recompute, machine API, serial or hardware dependency. Install in a separate environment:

```sh
uv venv /tmp/paste-cad-review-venv
uv pip install --python /tmp/paste-cad-review-venv/bin/python -r automation/paste/cad/requirements.txt
```

Run from this repository; redirect JSON to an evidence directory if desired:

```sh
/tmp/paste-cad-review-venv/bin/python automation/paste/cad/extract_brep.py ../paste-extruder-hardware/cad/OTS/luer.FCStd --object Body
/tmp/paste-cad-review-venv/bin/python automation/paste/cad/extract_brep.py ../paste-extruder-hardware/cad/FDM/extruder-base.FCStd --object Part__Mirroring --cylinder-radius 1.75
/tmp/paste-cad-review-venv/bin/python automation/paste/cad/extract_brep.py pnp/cad/assembly.FCStd --object b_FDM_0041_z_gantry_backplate_right_001_002 --cylinder-radius 1.75
/tmp/paste-cad-review-venv/bin/python automation/paste/cad/extract_brep.py pnp/cad/assembly.FCStd --object b_nozzle_holder_001_001 --object b_CSM_0001_staging_plate_001_
```

Every report binds both archive and extracted BREP hashes. Coordinates are cached shape coordinates including stored placement, not live machine coordinates. Do not apply XML placement twice. Cylinder axis origins can be anywhere along the cylinder axis; compare perpendicular coordinates or mating planes. Face bounds constrain the represented surface. A cylinder is not necessarily a drilled hole: classify against the surrounding solid.

The mounting review uses the extracted 15×10 pattern, outward-right mirrored orientation and front mating plane. It remains a candidate mate, not an automatically solved or physically calibrated rigid transform. See `../nominal-geometry-review.md`. The model does not contain a needle or full Luer outlet. No geometry output authorizes motion.

`check_n2_rise_nominal.py` follows the vendor top-assembly links, applies their top-level placements once, mates the final mirrored base to the right-backplate CAD hole pattern, and samples selected rigid solids across a hypothetical Z rise (default 22.4 mm at no more than 1 mm spacing). It reports OCC solid overlap plus exact shape distance for nearby selected machine solids, with the half-step Lipschitz lower bound. Run it with the pinned OCP environment:

```sh
/tmp/paste-cad-review-venv/bin/python automation/paste/cad/check_n2_rise_nominal.py --output /tmp/n2-rise-nominal.json
```

This is a model-only feasibility check. The assumed mating plane, raw-Z to CAD-Z relationship, movable-carriage classification, actual seated tip, harness flex and physical travel stops remain unverified. A zero overlap is not physical clearance certification or approval to perform the rise.
