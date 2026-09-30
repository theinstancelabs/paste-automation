#!/usr/bin/env python3
"""Nominal CAD collision sampling for the paste-head Z-rise hypothesis.

Offline only. Reads cached FreeCAD BREPs; does not launch FreeCAD or access the
machine. A possible collision is meaningful; no collision is only a partial
geometry result. This script intentionally does not claim a physical envelope.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

from OCP.BRep import BRep_Builder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepGProp import BRepGProp
from OCP.BRepTools import BRepTools
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.TopoDS import TopoDS_Shape
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Quaternion, gp_Trsf, gp_Vec


def prop(obj: ET.Element, name: str) -> ET.Element | None:
    return next((p for p in obj.findall('Properties/Property') if p.get('name') == name), None)


def object_by_name(root: ET.Element, name: str) -> ET.Element:
    return next(o for o in root.findall('ObjectData/Object') if o.get('name') == name)


def placement(obj: ET.Element) -> gp_Trsf:
    p = prop(obj, 'Placement')
    if p is None:
        return gp_Trsf()
    a = p.find('PropertyPlacement').attrib
    tr = gp_Trsf()
    tr.SetRotation(gp_Quaternion(float(a['Q0']), float(a['Q1']), float(a['Q2']), float(a['Q3'])))
    tr.SetTranslationPart(gp_Vec(float(a['Px']), float(a['Py']), float(a['Pz'])))
    return tr


def link_target(obj: ET.Element) -> tuple[str, str] | None:
    p = prop(obj, 'LinkedObject')
    if p is None:
        return None
    link = p.find('.//XLink')
    return (link.get('file'), link.get('name')) if link is not None else None


def cached_shape(hardware: Path, rel: str, name: str) -> TopoDS_Shape:
    """Follow external links to the terminal cached BREP; do not apply their placements."""
    archive_path = (hardware / rel).resolve()
    visited = set()
    while True:
        key = (str(archive_path), name)
        if key in visited:
            raise ValueError(f'Link cycle: {key}')
        visited.add(key)
        with zipfile.ZipFile(archive_path) as z:
            root = ET.fromstring(z.read('Document.xml'))
            obj = object_by_name(root, name)
            shp = prop(obj, 'Shape')
            part = shp.find('Part') if shp is not None else None
            if part is not None and part.get('file'):
                raw = z.read(part.get('file'))
                with tempfile.TemporaryDirectory(prefix='n2-rise-cad-') as td:
                    f = Path(td) / 'shape.brp'
                    f.write_bytes(raw)
                    shape = TopoDS_Shape()
                    BRepTools.Read_s(shape, str(f), BRep_Builder())
                    if shape.IsNull():
                        raise ValueError(f'Null cached shape: {archive_path}:{name}')
                    return shape
            target = link_target(obj)
            if target is None:
                raise ValueError(f'No terminal cached BREP or link: {archive_path}:{name}')
            child, name = target
            archive_path = (archive_path.parent / child).resolve()


def transformed(shape: TopoDS_Shape, tr: gp_Trsf) -> TopoDS_Shape:
    return BRepBuilderAPI_Transform(shape, tr, True).Shape()


def bounds(shape: TopoDS_Shape) -> list[float]:
    b = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, b, False, False)
    p, q = b.CornerMin(), b.CornerMax()
    return [round(v, 4) for v in (p.X(), p.Y(), p.Z(), q.X(), q.Y(), q.Z())]


def aabb_overlap(a: list[float], b: list[float]) -> bool:
    return all(a[i] <= b[i + 3] and b[i] <= a[i + 3] for i in range(3))


def aabb_distance(a: list[float], b: list[float]) -> float:
    gap = [max(0.0, b[i] - a[i + 3], a[i] - b[i + 3]) for i in range(3)]
    return math.sqrt(sum(x * x for x in gap))


def xy_aabb_distance(a: list[float], b: list[float]) -> float:
    gap = [max(0.0, b[i] - a[i + 3], a[i] - b[i + 3]) for i in range(2)]
    return math.hypot(*gap)


def common_volume(a: TopoDS_Shape, b: TopoDS_Shape) -> float:
    op = BRepAlgoAPI_Common(a, b)
    op.Build()
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(op.Shape(), props)
    return max(0.0, props.Mass())


def shape_distance(a: TopoDS_Shape, b: TopoDS_Shape) -> float:
    dist = BRepExtrema_DistShapeShape(a, b)
    dist.Perform()
    return float(dist.Value()) if dist.IsDone() else float('nan')


def root_members(root: ET.Element, group_name: str) -> list[ET.Element]:
    group = object_by_name(root, group_name)
    p = prop(group, 'Group')
    if p is None:
        return []
    return [object_by_name(root, x.get('value')) for x in p.findall('.//Link')]


def compose(a: gp_Trsf, b: gp_Trsf) -> gp_Trsf:
    out = gp_Trsf()
    out.SetValues(*(a.Value(i, j) for i in range(1, 4) for j in range(1, 5)))
    out.Multiply(b)
    return out


def translation_z(mm: float) -> gp_Trsf:
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(0, 0, mm))
    return t


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--machine', type=Path, default=Path('pnp/cad/assembly.FCStd'))
    ap.add_argument('--hardware', type=Path, default=Path('/home/lumen/paste-extruder-hardware'))
    ap.add_argument('--rise-mm', type=float, default=22.4)
    ap.add_argument('--step-mm', type=float, default=1.0)
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    if args.rise_mm <= 0 or args.step_mm <= 0 or not all(map(math.isfinite, (args.rise_mm, args.step_mm))):
        ap.error('rise/step must be finite and positive')

    top = args.hardware / 'cad/top-assembly.FCStd'
    with zipfile.ZipFile(top) as z:
        root = ET.fromstring(z.read('Document.xml'))

    # Fit final mirrored base's 15x10 bore pattern to the machine's right
    # backplate pattern. The existing review establishes the candidate mating
    # plane and bore centers; actual installed transform is not verified.
    # In the final-mirrored source, the two X-row bore centers differ by
    # (-14.909714,-1.643294). A -6.3deg Z rotation aligns them to machine -X.
    # The transfer is anchored to the candidate front plane Y=171.154 and the
    # lower-right CAD bore X=471.289,Z=140.589.
    rz = gp_Trsf()
    rz.SetRotation(gp_Quaternion(0, 0, math.sin(math.radians(-6.3) / 2), math.cos(math.radians(-6.3) / 2)))
    rz.SetTranslationPart(gp_Vec(471.289, 166.154, 140.589))
    base = object_by_name(root, 'Body')
    base_to_local = placement(base)
    machine_from_local = compose(rz, base_to_local.Inverted())

    members = []
    for group_name in ('Assembly001', 'Assembly002'):
        group = object_by_name(root, group_name)
        group_tr = placement(group)
        for obj in root_members(root, group_name):
            label = prop(obj, 'Label')
            label = label.find('String').get('value') if label is not None else obj.get('name')
            # Keep the principal rigid solids. Small fasteners add no useful
            # obstacle coverage and make repeated booleans slower.
            if label not in {'Body', 'Nema-11', 'Body001', 'Body002', 'Body003', 'Body004', 'Body005', 'M3x70-ThreadedRod'}:
                continue
            target = link_target(obj)
            if target is None:
                continue
            shape = cached_shape(args.hardware / 'cad', target[0], target[1])
            obj_tr = compose(group_tr, placement(obj))
            machine_tr = compose(machine_from_local, obj_tr)
            members.append({'name': obj.get('name'), 'label': label,
                            'shape': transformed(shape, machine_tr),
                            'source': f'{target[0]}:{target[1]}'})

    # Cached machine assembly objects are world-coordinate shapes. These are
    # candidates for fixed obstacles; the right Z-carriage/backplate are not
    # included here because they move with the paste head.
    machine_file = args.machine.resolve()
    fixed_names = [
        'b_FDM_0011_x_gantry_front_001_001',
        'b_x_gantry_back_001_002',
        'b_y_gantry_right_001_',
        'b_y_gantry_001_002',
    ]
    fixed = [{'name': n, 'shape': cached_shape(machine_file.parent, machine_file.name, n)} for n in fixed_names]
    for obstacle in fixed:
        obstacle['bounds'] = bounds(obstacle['shape'])

    # Evaluate the full linear interval at at most one-mm spacing, including
    # both endpoints. This is nominal CAD overlap detection, not a clearance
    # tolerance or a physical/cable sweep certification.
    nsteps = math.ceil(args.rise_mm / args.step_mm)
    steps = [args.rise_mm * i / nsteps for i in range(nsteps + 1)]
    contacts = []
    clearance_samples = []
    horizontal_bounds = []
    for dz in steps:
        shift = translation_z(dz)
        for member in members:
            moved = transformed(member['shape'], shift)
            moved_bounds = bounds(moved)
            for obstacle in fixed:
                box_gap = aabb_distance(moved_bounds, obstacle['bounds'])
                xy_gap = xy_aabb_distance(moved_bounds, obstacle['bounds'])
                if xy_gap > 0:
                    # Pure Z translation cannot change this conservative XY
                    # separation; it bounds the whole continuous sweep.
                    horizontal_bounds.append({'moving': member['label'], 'fixed': obstacle['name'],
                                              'horizontalAabbLowerBoundMm': round(xy_gap, 4)})
                elif box_gap <= 12.0:
                    d = shape_distance(moved, obstacle['shape'])
                    clearance_samples.append({'riseMm': round(dz, 3), 'moving': member['label'],
                                              'fixed': obstacle['name'], 'aabbLowerBoundMm': round(box_gap, 4),
                                              'minimumDistanceMm': round(d, 4) if math.isfinite(d) else None})
                if not aabb_overlap(moved_bounds, obstacle['bounds']):
                    continue
                vol = common_volume(moved, obstacle['shape'])
                if vol > 1e-4:
                    contacts.append({'riseMm': round(dz, 3), 'moving': member['label'],
                                     'fixed': obstacle['name'], 'intersectionVolumeMm3': round(vol, 3)})
    exact_min = min((x['minimumDistanceMm'] for x in clearance_samples if x['minimumDistanceMm'] is not None), default=None)
    report = {
        'kind': 'nominal-cad-rise-overlap-sampling',
        'nominalOnly': True,
        'physicalClearanceEstablished': False,
        'riseMm': args.rise_mm,
        'sampleStepMaxMm': args.rise_mm / nsteps,
        'sampleCount': len(steps),
        'machineCadSha256': hashlib.sha256(machine_file.read_bytes()).hexdigest(),
        'hardwareTopAssemblySha256': hashlib.sha256(top.read_bytes()).hexdigest(),
        'mountAssumptions': {
            'candidateBaseToRightBackplateMatingPlane': True,
            'rotationAboutZDeg': -6.3,
            'planeYmm': 171.154,
            'anchorBoreXmm': 471.289,
            'anchorBoreZmm': 140.589,
            'rawZToCadZRegistration': None,
            'installedNeedleAndCableGeometryIncluded': False,
        },
        'movingParts': [{'name': m['name'], 'label': m['label'], 'source': m['source'],
                         'startBoundsMm': bounds(m['shape']),
                         'endBoundsMm': bounds(transformed(m['shape'], translation_z(args.rise_mm)))} for m in members],
        'fixedMachineBrepNames': fixed_names,
        'sweepWideXYBounds': horizontal_bounds,
        'minimumHorizontalAabbLowerBoundMm': min((x['horizontalAabbLowerBoundMm'] for x in horizontal_bounds), default=None),
        'nearbyClearanceSamples': clearance_samples,
        'minimumSampledClearanceMm': exact_min,
        'betweenSampleTranslationLowerBoundMm': (exact_min - args.rise_mm / nsteps / 2) if exact_min is not None else None,
        'nominalSolidIntersections': contacts,
        'interpretation': 'Positive horizontal AABB gaps are Z-independent conservative lower bounds for the continuous vertical sweep of the selected rigid shapes against selected fixed solids. Exact shape distances for XY-overlapping pairs are sampled with half-step Lipschitz bounds. Neither method establishes raw-Z correspondence, actual installation, motion limits, flexible cable/harness clearance, or physical safety.',
    }
    encoded = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(encoded + '\n')
    print(encoded)


if __name__ == '__main__':
    main()
