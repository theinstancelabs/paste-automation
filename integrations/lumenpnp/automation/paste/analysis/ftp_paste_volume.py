#!/usr/bin/env python3
"""Offline stencil-equivalent paste volume scenarios for the canonical FTP resistor pads."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BOARD = ROOT / 'pnp/pcb/ftp/ftp.kicad_pcb'
EXTRACTOR = Path(__file__).resolve().parents[1] / 'pads/extract_ftp_pads.py'


def load_pad_extractor():
    spec = importlib.util.spec_from_file_location('ftp_pad_geometry', EXTRACTOR)
    if spec is None or spec.loader is None:
        raise ValueError('Could not load the offline FTP pad geometry extractor')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def volume_scenario(area_mm2, thickness_mm):
    if type(area_mm2) not in (int, float) or not math.isfinite(area_mm2) or area_mm2 <= 0:
        raise ValueError('Pad area must be finite and positive')
    if type(thickness_mm) not in (int, float) or not math.isfinite(thickness_mm) or not 0 < thickness_mm <= 1:
        raise ValueError('Stencil thickness must be in (0, 1] mm')
    volume_mm3 = area_mm2 * thickness_mm
    return {
        'stencilThicknessMm': thickness_mm,
        'pasteApertureAreaMm2': area_mm2,
        'volumeMm3': volume_mm3,
        'volumeNL': volume_mm3 * 1000,
        'idealizedHemisphereDiameterMm': (12 * volume_mm3 / math.pi) ** (1 / 3),
        'idealizedSphereDiameterMm': (6 * volume_mm3 / math.pi) ** (1 / 3),
    }


def build(board_path, thicknesses):
    board_path = Path(board_path).resolve(strict=True)
    board_bytes = board_path.read_bytes()
    extractor = load_pad_extractor()
    pads = extractor.extract_kicad(board_bytes.decode('utf-8'))
    if len(pads) != 80 or {p['reference'] for p in pads} != {f'R{i}' for i in range(1, 41)}:
        raise ValueError('Expected exactly the 80 paste pads for R1–R40')
    if len({p['id'] for p in pads}) != 80:
        raise ValueError('Pad IDs must be unique')
    scenarios = []
    for thickness in thicknesses:
        if type(thickness) not in (int, float) or not math.isfinite(thickness) or not 0 < thickness <= 1:
            raise ValueError('Each stencil thickness must be finite and in (0, 1] mm')
        scenarios.append({
            'stencilThicknessMm': thickness,
            'pads': [
                {'padId': pad['id'], 'apertureAreaMm2': pad['areaMm2'],
                 **volume_scenario(pad['areaMm2'], thickness)}
                for pad in pads
            ],
        })
    extractor_bytes = EXTRACTOR.read_bytes()
    return {
        'schema': 1,
        'kind': 'offline-ftp-stencil-equivalent-paste-volume-scenarios',
        'source': {
            'board': {'path': str(board_path), 'sha256': hashlib.sha256(board_bytes).hexdigest(),
                      'bytes': len(board_bytes)},
            'padExtractor': {'path': str(EXTRACTOR),
                             'sha256': hashlib.sha256(extractor_bytes).hexdigest()},
            'padCount': len(pads),
            'padIds': [pad['id'] for pad in pads],
        },
        'calculation': {
            'method': 'roundrect KiCad paste aperture area multiplied by nominal stencil thickness',
            'volumeUnits': '1 mm3 = 1000 nL',
            'transferAssumptions': {'fullApertureFill': True, 'pasteTransferEfficiency': 1.0,
                                    'interpretation': 'idealized 100% transfer; actual deposited volume is unmeasured'},
            'shapeModels': {
                'hemisphereDiameterMm': '(12 * volumeMm3 / pi)^(1/3)',
                'sphereDiameterMm': '(6 * volumeMm3 / pi)^(1/3)',
                'label': 'Idealized equivalent shapes only; not inferred from camera images or physical deposits.',
            },
        },
        'scenarios': scenarios,
        'status': {'candidateOnly': True, 'acceptanceLimits': None,
                   'machineMotionAllowed': False, 'flowCalibrated': False,
                   'motorDegrees': None},
        'limitations': [
            'Calculated from CAD paste apertures and hypothetical stencil thickness only.',
            'Does not establish stencil fill, transfer efficiency, paste rheology, deposit shape, or actual volume.',
            'Idealized hemisphere and sphere diameters are geometry comparisons, not camera-derived measurements.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board', type=Path, default=DEFAULT_BOARD)
    parser.add_argument('--stencil-thickness-mm', type=float, nargs='+', default=[0.10, 0.125, 0.15])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = build(args.board, args.stencil_thickness_mm)
        encoded = json.dumps(result, indent=2, allow_nan=False) + '\n'
        if args.output:
            with args.output.open('x', encoding='utf-8') as stream:
                stream.write(encoded)
            destination = str(args.output.resolve())
        else:
            sys.stdout.write(encoded)
            destination = None
    except (OSError, ValueError, UnicodeError) as exc:
        parser.error(str(exc))
    if destination:
        print(json.dumps({'output': destination, 'padCount': result['source']['padCount'],
                          'scenarios': len(result['scenarios']), 'machineMotionAllowed': False}))


if __name__ == '__main__':
    main()
