#!/usr/bin/env python3
"""Build unreviewed affine-registration candidates from a camera acquisition manifest.

This is an offline adapter only. It derives image centers/Jacobian candidates
from the measured reports and emits a registration input with all human-review
fields false/empty. It never claims identity review or registration acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path

from measure_fresh_registration_centers import analyze as measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def image_evidence(report_path):
    p = Path(report_path).resolve(strict=True)
    report = json.loads(p.read_text())
    im = report.get('afterImages', {}).get('top', {})
    image = (p.parent / im['path']).resolve(strict=True)
    if image.parent != p.parent:
        raise ValueError('Camera image must remain beside its source report')
    return {'path': str(image), 'sha256': sha(image)}


def first(records, name):
    matches = [r for r in records if r.get('name') == name]
    if not matches:
        raise ValueError(f'Missing acquisition record: {name}')
    return matches[-1]


def candidate(manifest_path, measurement_path, output_dir):
    manifest_path = Path(manifest_path).resolve(strict=True)
    measurement_path = Path(measurement_path).resolve(strict=True)
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=False)
    acq = json.loads(manifest_path.read_text())
    measurements = json.loads(measurement_path.read_text())
    if (acq.get('kind') != 'current-session-affine-registration-acquisition'
            or acq.get('acceptanceEstablished') is not False):
        raise ValueError('Expected non-accepted current-session acquisition manifest')
    centers = measure(measurements)
    jac = centers['jacobianCandidate']
    sess = centers['session']
    jacobian = {
        'schema': 1, 'scope': 'measured-top-camera-image-jacobian-candidate',
        'session': sess, 'fixedRawZAB': centers['fixedRawZAB'],
        'pixelShiftPerCameraMm': jac['pixelShiftPerCameraMm'],
        'sourceMeasurements': jac['sourceMeasurements'],
        'reviewRequired': ['Confirm the same physical FID2 feature in base, xplus, and yplus images.'],
        'reviewedBy': '', 'reviewedMs': None,
        'physicalCalibrationEstablished': False,
    }
    jac_path = out / 'candidate-image-jacobian.json'
    jac_path.write_text(json.dumps(jacobian, indent=2, allow_nan=False) + '\n')

    records = acq.get('records', [])
    jac_base_report = Path(measurements['jacobianSamples'][0]['report']).resolve(strict=True)
    refs = {
        'FID1': next((r for r in reversed(records) if r.get('name', '').startswith('FID1-center-')), None),
        'FID2': next((r for r in records if Path(r.get('report', '')).resolve() == jac_base_report), None),
        'FID3': next((r for r in reversed(records) if r.get('name', '').startswith('FID3-center-')), None),
    }
    if any(v is None for v in refs.values()):
        raise ValueError('Acquisition must contain centered FID1/FID2/FID3 camera reports')
    fid_measurements = {}
    for ref, rec in refs.items():
        report = Path(rec['report']).resolve(strict=True)
        fid_measurements[ref] = {
            'report': str(report), 'reportSha256': sha(report),
            'topImageSha256': image_evidence(report)['sha256'],
            'fiducialIdentityReviewed': False,
            'centeredInTopImageReviewed': False,
        }
    pads = []
    pad_candidates = {p['padId']: p for p in centers['heldOutPadCenterCandidates']}
    heldout_ids = centers.get('heldOutPadIds', acq.get('heldOutPadIds', ['R1.2', 'R16.1', 'R40.1']))
    if heldout_ids not in (['R1.2', 'R16.1', 'R40.1'], ['R1.2', 'R16.1', 'R24.1']):
        raise ValueError('Acquisition manifest has an unsupported held-out set')
    for pad_id in heldout_ids:
        p = pad_candidates[pad_id]
        pads.append({
            'padId': pad_id, 'report': p['report'], 'reportSha256': p['reportSha256'],
            'topImageSha256': p['topImageSha256'],
            'observedCenterPixel': p['observedCenterPixel'],
            'padIdentityReviewed': False, 'centerMeasurementReviewed': False,
        })
    request = {
        'schema': 1, 'scope': 'fresh-ftp-top-camera-fiducials', 'operator': '',
        'board': '/home/lumen/lumenpnp/pnp/pcb/ftp/ftp.kicad_pcb',
        'measurements': fid_measurements,
        'roi': [800, 400, 1100, 700], 'thresholds': [100, 120, 140],
        'registrationModel': 'three-fiducial-affine',
        'heldOutPadChecks': pads,
        'imageJacobianEvidence': {'path': str(jac_path), 'sha256': sha(jac_path)},
        'reviewRequired': ['Set operator after review; verify all three fiducial identities and centering.',
                           'Verify held-out resistor pad identities and image centers.',
                           'Review candidate Jacobian source images.'],
        'acceptanceEstablished': False,
    }
    req_path = out / 'candidate-registration-input.json'
    req_path.write_text(json.dumps(request, indent=2, allow_nan=False) + '\n')
    center_path = out / 'candidate-centers-and-jacobian.json'
    center_path.write_text(json.dumps(centers, indent=2, allow_nan=False) + '\n')
    return {'candidateRegistrationInput': str(req_path), 'candidateJacobian': str(jac_path),
            'candidateMeasurements': str(center_path), 'reviewRequired': True,
            'acceptanceEstablished': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--acquisition-manifest', required=True)
    p.add_argument('--measurements-input', help='Defaults to sibling measurements-input.json')
    p.add_argument('--output', required=True, help='New output directory')
    a = p.parse_args()
    manifest = Path(a.acquisition_manifest).resolve(strict=True)
    measurement = Path(a.measurements_input).resolve(strict=True) if a.measurements_input else manifest.parent / 'measurements-input.json'
    print(json.dumps(candidate(manifest, measurement, a.output), indent=2))


if __name__ == '__main__':
    main()
