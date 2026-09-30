#!/usr/bin/env python3
"""Read cached FreeCAD BREP bounds/cylinders; no FreeCAD recompute or machine IO."""
import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
from OCP.BRep import BRep_Builder
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepTools import BRepTools
from OCP.Bnd import Bnd_Box
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape


def xyz(point):
    return [point.X(), point.Y(), point.Z()]


def bounds(shape):
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    return xyz(box.CornerMin()) + xyz(box.CornerMax())


def extract(path, objects=(), radius=None):
    records = []
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with zipfile.ZipFile(path) as archive, tempfile.TemporaryDirectory(prefix='paste-cad-') as tmp:
        root = ET.fromstring(archive.read('Document.xml'))
        for obj in root.findall('ObjectData/Object'):
            if objects and obj.get('name') not in objects:
                continue
            props = {p.get('name'): p for p in obj.findall('Properties/Property')}
            part = props.get('Shape')
            part = part.find('Part') if part is not None else None
            if part is None or not part.get('file'):
                continue
            raw = archive.read(part.get('file'))
            cached = Path(tmp) / 'shape.brp'
            cached.write_bytes(raw)
            shape = TopoDS_Shape()
            BRepTools.Read_s(shape, str(cached), BRep_Builder())
            if shape.IsNull():
                raise ValueError(f'Null BREP: {path}:{obj.get("name")}')
            cylinders = []
            iterator = TopExp_Explorer(shape, TopAbs_FACE)
            while iterator.More():
                face = TopoDS.Face(iterator.Current())
                surface = BRepAdaptor_Surface(face)
                if surface.GetType() == GeomAbs_Cylinder:
                    cylinder = surface.Cylinder()
                    if radius is None or abs(cylinder.Radius() - radius) <= 1e-6:
                        cylinders.append({'radiusMm': cylinder.Radius(),
                                          'axisOriginMm': xyz(cylinder.Location()),
                                          'axisDirection': xyz(cylinder.Axis().Direction()),
                                          'faceBoundsMm': bounds(face)})
                iterator.Next()
            label = props.get('Label')
            placement = props.get('Placement')
            records.append({'object': obj.get('name'),
                            'label': label.find('String').get('value') if label is not None else None,
                            'cachedBrep': part.get('file'), 'cachedBrepSha256': hashlib.sha256(raw).hexdigest(),
                            'boundsMm': bounds(shape), 'cylinders': cylinders,
                            'xmlPlacementReferenceOnly': dict(placement.find('PropertyPlacement').attrib) if placement is not None else None})
    missing = set(objects) - {r['object'] for r in records}
    if missing:
        raise ValueError(f'Objects absent or without cached BREP: {sorted(missing)}')
    return {'source': str(path.resolve()), 'sha256': digest, 'nominalOnly': True,
            'units': 'millimeters', 'placementAlreadyInCachedBrep': True,
            'objects': records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fcstd', type=Path)
    parser.add_argument('--object', action='append', default=[])
    parser.add_argument('--cylinder-radius', type=float)
    args = parser.parse_args()
    print(json.dumps(extract(args.fcstd, args.object, args.cylinder_radius), indent=2))


if __name__ == '__main__':
    main()
