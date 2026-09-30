# Nominal paste-head geometry review

2026-09-30. Independent read-only CAD inspection; no motion, serial connection, machine setting changes, or physical calibration. Hardware source commit `d1aa6cda9d3e40b7f3fbe797b8b84fd1cb556d55`; machine source `5ec657b34fbf1f4e2f1bc2ade36a16c438070b10` (`v4.1.0-3-g5ec657b`). This establishes a usable nominal model with explicit unknowns, not a measured machine profile.

## Method and reproducibility

Read repository AGENTS and hardware README. Native files are FreeCAD FCStd ZIP archives, containing Document.xml parameters and cached OpenCascade BREP solids. Parsed XML directly; independently read BREP using cadquery-ocp8.0.1.0.0 in temporary `/tmp/paste-cad-review-venv`, with BRepTools.Read, BRepBndLib.AddOptimal (no triangulation/tolerance inflation), and BRepAdaptor_Surface cylinder extraction. No CAD recompute was performed. Canonical repeatable extraction is preserved in `cad/extract_brep.py`, with pinned `cadquery-ocp==8.0.1.0.0` in `cad/requirements.txt` and complete run commands in `cad/README.md`. It reproduces syringe bounds/cylinders and right-backplate mounting features; both were rerun and checked. Temporary session outputs are not required. BREP coordinates already include saved shape placement: applying Document.xml placements again to cached assembly solids would double-transform them.

## Extracted nominal dimensions (mm)

| Feature | Evidence/result |
|---|---|
| Right-hand mirror | README requires final mirror for base and clamp. Both Part__Mirroring objects reflect X about YZ; extruder assembly links these final mirrored objects. Do not mirror them twice. |
| Base mounting pattern | Four cylindrical through bores radius1.75, with counterbores radius3.5, form15×10 rectangle. Axes are approximately(0.10956,-0.99398,0) in saved base coordinates. |
| Barrel axis relative to lower-right mounting hole | Approximately18.5 outward horizontally and14.5 forward, perpendicular to mounting plane. Base barrel seat/bore radius5.9. These are local physical CAD dimensions, not OpenPnP offsets. |
| Simplified syringe barrel | OTS/luer.FCStd Body has coaxial cylinder surfaces radius4.75 and5.85: nominal ID9.50 and OD11.70. Axial extent -56..0, flange to+1.9. Envelope X±11.772, Y±6.524, Z-56..+1.9. The model is a simple open barrel/flange; no separate Luer outlet, needle hub, or needle solid is present. |
| Cartridge assembly | Syringe identity placement in cartridge; cartridge top-level placement(21.0230,-15.6801,25.0000), rotation approximately-90°Z. Thus simplified barrel bottom lies at top-assembly Z~-31. This assembly is not yet mated to machine CAD. |
| Gears |19 motor teeth and32 cartridge teeth, both module1. Ratio magnitude19/32=0.59375 cartridge rev/motor rev; rotation sign and controller direction remain separate. |
| Threaded rod | cartridge-assembly ThreadedRod active Diameter=M3, Length70, LeftHanded=false, Thread=true. Base64 JSON Proxy stores dimTable[0.5,480,502], consistent with nominal M3 coarse0.5mm pitch. PitchCustom1.0 belongs to inactive Custom diameter and must not be used as the pitch. |
| User's needle | User-specified22ga,1/4inch gives nominal metal tube length6.35. Gauge/length do not specify seated Luer hub-to-tip reach. Do not add6.35 directly to the simplified open barrel bottom as a full tip offset. |

Using CAD bore9.5, nominal pitch0.5 and gearing19/32 gives plunger advance0.296875mm/motor revolution, with ideal displaced volume approximately21.043µL/revolution. This is a nominal piston-volume model, not delivered paste: compliance, bubbles, backlash, leakage, needle resistance and paste condition require empirical coupon tests. It does not authorize a B-axis command.

## Candidate mate into actual v4.1 assembly

Machine assembly cached right-backplate BREP contains the corresponding four radius1.75 mounting holes, axes parallelY. Rounded centers(X,Z) are(456.289,140.589),(471.289,140.593),(456.287,150.589),(471.287,150.593). The front mating plane is approximatelyY171.154. The stock gantry has alternative15×10 patterns separated7.4 laterally; the assembled backplate resolves which physical mounting pattern is relevant.

Matching the final mirrored base's four-hole pattern and bore axes to the machine right-backplate pattern, with the base mounting plane on the backplate front face, gives a **candidate** barrel axis near machine-CAD (X,Y)=(489.80,151.66), flange Z~165.59 and simplified barrel bottom Z~109.59. The stock right-nozzle-holder axis is (467.491,152.054), so this CAD mate implies about (+22.31,-0.39) mm. This replaces the earlier +4.60 mm Y estimate, which used an inconsistent mounting datum. A later camera-plane observation found the new needle at (+21.381,+0.059) relative to the legacy N2 XY; its close agreement supports this as a nominal prior only, not a calibrated offset. The complete assembly mate, seated needle, and model/world-to-controller transform remain unverified. See the repeatable sampled-rigid-solid analysis in `cad/check_n2_rise_nominal.py`; it is not a motion authorization.

Stock nozzle-holder center separation is47.416mm in CAD, while saved prior nozzle calibration has47.793mm separation. Those values confirm order of magnitude but cannot determine a new extruder offset. New image shows larger head separation, qualitatively consistent with outward-shifted syringe. No saved nozzle offset was rewritten.

## Z envelope and camera cross-check

Machine-CAD staging plates have topZ42.973, thickness3, and600×120 outlines. The assembly is a saved static pose, not a mechanical travel envelope or homed pose. The candidate barrel bottom is therefore~66.62 above its plate at that assembly pose **before** adding the real outlet/hub/needle and mapping assembly Z into machine coordinates. This is useful for checking a digital model, but does not prove an unplatformed coupon is reachable.

Native controller model has opposing Z: z2=63-z1, home31.5, saved joint safe raw interval26.5..36.5. The63 mapping must not be interpreted as verified physical travel; prior controller clamping produced software/physical divergence. Usable reach must intersect controller limits, both-head collision envelopes, true seated tip length and observed target surface. Lowering N2 raises N1 under this mapping; moving either still requires clearance of all moving head solids.

Stationary1920×1080 evidence `automation/evidence/paste-coupon-overview-1790759147/frame-029.jpg` shows separate tip silhouettes above nearby camera/board fixtures. Nominal6.35mm exposed needle over roughly16 pixels suggests~0.4mm/pixel locally, useful only as a coarse scale prior. Different object depths, projection and uncertain exposed length prohibit transferring that directly into a metric target-surface gap. The image supports a short bounded constant-raw-Z lateral camera survey if parent verifies the full path, start pose and pureXY transform; it does not establish an approach height or dispensing reach.

## Calibration work implied by this model

Use the CAD mount/axis as nominal prior. Register known staging-plate grid to the current camera image; use known head/mount feature points for the elevated plane. Identify seated hub geometry and tip endpoint from a close stationary view or matching manufacturer drawing. Capture paired same-target top-camera/tip observations to estimate only manufacturing/seating deviations from the nominal transform. Map target surface and the two actual head-tip envelopes to the current controller pose, then verify small supervised moves through the established owner. Keep records session/config/hash-bound. No requirement to replace this workflow with a full manual ruler survey, but unresolved image depth cannot be represented as measured clearance.

Parent's `extract-cad-parameters.py` was read independently: ratios/formulas are consistent; it emits nominalOnly/physicalCalibrationEstablished=false and keeps explicit pitch/bore inputs unverified. It does not derive mounted offsets or output motion. Source hashes and conditional inputs should travel with any downstream nominal-model record.

## Source hashes (SHA-256)

- `/home/lumen/paste-extruder-hardware/README.md`: `7e79828c8786b31216b0230fa1b26119ea16b89e163ea08ea0938ff94d7b13c1`
- `/home/lumen/paste-extruder-hardware/cad/FDM/extruder-base.FCStd`: `90f1ad142c5af2185eed8f184c8a8339129d38957734e43ece9a5293ba27a90d`
- `/home/lumen/paste-extruder-hardware/cad/FDM/cartridge-clamp.FCStd`: `d776ea7bd76aac292e61189bf339fb855c7163e9a0c19d1fce77d44fc029b7d7`
- `/home/lumen/paste-extruder-hardware/cad/OTS/luer.FCStd`: `c5db51c11f240c3e7ebc5620487ccaa7f959f58ad777da79e5edf19de668dc40`
- `/home/lumen/paste-extruder-hardware/cad/cartridge-assembly.FCStd`: `7792a91f9d31f8cab5ca7f5794017110f4f6eab1f6e49e1f7ae3745cbe22c3cc`
- `/home/lumen/paste-extruder-hardware/cad/top-assembly.FCStd`: `812d6504c8c0ebcf0d300155ec8a65b70c053118deaacf0a509f9deeb16a0576`
- `/home/lumen/paste-extruder-hardware/cad/FDM/extruder-gear.FCStd`: `05f19542631bc6ec682a87cb56e462017017bd7c76c39d9dd9403ddf2cf7adf1`
- `/home/lumen/paste-extruder-hardware/cad/FDM/cartridge-gear.FCStd`: `0ee74163ca0aa44ec2426cc6847068d1343dae6abadefd61cec82e11b4d62b86`
- `/home/lumen/lumenpnp/pnp/cad/assembly.FCStd`: `cffa43d966aa77699f244a7c3b87232640d43b7a99fc28db05af4e4328f5ef6b`
- `/home/lumen/lumenpnp/pnp/cad/FDM/z-gantry.FCStd`: `61ce3ddfd9690137870c09b4a134fba2039626b1b6c5a99d6be7e5559a96e065`
- `/home/lumen/lumenpnp/pnp/cad/FDM/z-gantry-backplate-right.FCStd`: `8cde0539656bfd319c737e1b52441f331fd1a90884cd8053fd7126fbaabc1019`
