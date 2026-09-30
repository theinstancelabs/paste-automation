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
