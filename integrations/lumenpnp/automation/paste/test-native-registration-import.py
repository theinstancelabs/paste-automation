import hashlib
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

SCRIPT = Path(__file__).with_name('prepare-native-registration-import.py')
spec = importlib.util.spec_from_file_location('native_import', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(root):
    session = '27c1ab29-a268-47d7-8dcf-eaf2a71ade02'
    pid = 'a' * 64
    config = 'b' * 64
    raw = {'X': 250.0, 'Y': 180.0, 'Z': 32.25, 'A': 200.0, 'B': -100.0}
    poses = {h: {'x': 250.0, 'y': 180.0, 'z': 32.25, 'rotation': 0.0}
             for h in ('N1', 'N2', 'top', 'bottom')}
    pads = {}
    for i in range(1, 41):
        for prefix in ('R', 'D'):
            ref = prefix + str(i)
            x, y = 100.0 + i * .3, 100.0 + i * .2 + i * i * .01
            pads[ref] = {'1': {'cameraXY': [x, y], 'tipXY': [x - 1, y - 2], 'gapAtWorkZ': None},
                         '2': {'cameraXY': [x + .1, y + .05], 'tipXY': [x - .9, y - 1.95], 'gapAtWorkZ': None}}
    board = mod.FTP_BOARD
    native_tree = ET.parse(mod.NATIVE_JOB)
    native_location = native_tree.getroot().find(".//object[@class='org.openpnp.model.BoardLocation']")
    native_board = ET.parse(native_location.get('file-name')).getroot()
    for placement in native_board.findall('./placements/placement'):
        placement.set('enabled', 'false')
    inspect_board = root / 'inspect.board.xml'
    ET.ElementTree(native_board).write(inspect_board, encoding='utf-8', xml_declaration=True)
    job = root / 'job.xml'
    job_xml = ET.Element('job')
    ET.SubElement(job_xml, 'object', {'class': 'org.openpnp.model.BoardLocation', 'side': 'Top',
                                     'file-name': str(inspect_board)})
    ET.ElementTree(job_xml).write(job, encoding='utf-8', xml_declaration=True)
    profile = {'schema': 1, 'id': pid, 'sessionId': session, 'name': 'fixture', 'jvmStartMs': 123456,
               'liveConfigurationSha256': config, 'safeZ': 32.25, 'travelZ': 53.45, 'workZ': 60.0,
               'gapUncertaintyMm': .3, 'heightCalibrationPending': True,
               'rawBounds': {a: {'min': lo, 'max': hi} for a, lo, hi in
                             [('X', 0, 500), ('Y', 0, 500), ('Z', 0, 63), ('A', 0, 360), ('B', -20000, 20000)]},
               'headClearanceBounds': {h: {'minX': 0, 'maxX': 500, 'minY': 0, 'maxY': 500, 'minZ': 0, 'maxZ': 63}
                                       for h in ('N1', 'N2')},
               'expectedRaw': raw, 'expectedDriver': dict(raw), 'expectedNativePoses': poses,
               'pads': pads, 'boardEvidence': {'path': str(board), 'sha256': sha(board)},
               'inspectionJob': str(job),
               'sourceEvidence': [{'path': str(board), 'sha256': sha(board)},
                                  {'path': str(job), 'sha256': sha(job)}],
               'rodBudget': {'baselineGrossDegrees': 0, 'baselineB': -100.0,
                             'maximumAdditionalGrossDegrees': 1000},
               'cameraMinusTipXYMm': [1.0, 2.0]}
    sidecar = {'schema': 1, 'profileId': pid, 'sessionId': session, 'jvmStartMs': 123456,
               'configurationSha256': config, 'alignmentSamples': [], 'zSamples': [], 'ztouchSamples': [],
               'alignmentApplied': False, 'zApplied': False, 'boardTouchReference': None,
               'vacuumReference': None, 'needleTouchMeasurement': None}
    parser = SCRIPT.parent / 'pads/extract_ftp_pads.py'
    sources = []
    finished = datetime.now(timezone.utc).isoformat()
    for i in range(3):
        report = {'scope': 'native-current-pose-fiducial-vision',
                  'status': 'completed-native-fiducial-detection-awaiting-review',
                  'jobPath': str(mod.NATIVE_JOB), 'requestId': f'report-{i}',
                  'finishedAt': finished}
        item = write(root / f'source-{i}.json', report)
        sources.append({'path': str(item), 'sha256': sha(item)})
    registration = {'schema': 1, 'scope': mod.NATIVE_SIMILARITY_SCOPE,
                    'acceptance': {'passed': True}, 'physicalRegistrationEstablished': False,
                    'executionReady': False, 'motionDispatched': False,
                    'machineConfigurationChanged': False, 'jobChanged': False,
                    'session': {'jvmStartMs': 123456, 'liveConfigurationSha256': config},
                    'board': {'path': str(board), 'sha256': sha(board)},
                    'parser': {'path': str(parser), 'sha256': sha(parser)},
                    'nativeSource': {'reports': sources, 'sourceBarriers': [], 'jobPath': str(mod.NATIVE_JOB)},
                    'measurements': {ref: {'reportId': f'report-{i}', 'finishedAt': finished,
                                           'report': sources[i]}
                                     for i, ref in enumerate(('FID1', 'FID2', 'FID3'))},
                    'resistorPadMachineXYTargets': []}
    for i in range(1, 41):
        ref = 'R' + str(i)
        for pad in ('1', '2'):
            old = profile['pads'][ref][pad]['cameraXY']
            registration['resistorPadMachineXYTargets'].append(
                {'padId': ref + '.' + pad, 'machineXYMm': [old[0] + .1, old[1] - .1]})
    return profile, sidecar, registration


class NativeImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        mod.FTP_BOARD = write(self.root / 'ftp.kicad_pcb', {'board': 'canonical-test-fixture'})
        source_board = ET.Element('openpnp-board', {'version': '1.1', 'name': 'native-test.board.xml'})
        placements = ET.SubElement(source_board, 'placements')
        for ident in [f'{prefix}{i}' for prefix, count in (('R', 40), ('D', 40)) for i in range(1, count + 1)] + ['FID1', 'FID2', 'FID3']:
            part = 'resistor' if ident.startswith('R') else ('diode' if ident.startswith('D') else 'fiducial')
            ET.SubElement(placements, 'placement', {'id': ident, 'part-id': part, 'side': 'Top',
                                                    'enabled': 'true' if ident == 'R2' else 'false'})
        native_board_path = self.root / 'native-test.board.xml'
        ET.ElementTree(source_board).write(native_board_path, encoding='utf-8', xml_declaration=True)
        native_job_root = ET.Element('job')
        ET.SubElement(native_job_root, 'object', {'class': 'org.openpnp.model.BoardLocation', 'side': 'Top',
                                                 'file-name': str(native_board_path)})
        mod.NATIVE_JOB = self.root / 'native-test.job.xml'
        ET.ElementTree(native_job_root).write(mod.NATIVE_JOB, encoding='utf-8', xml_declaration=True)
        mod.NATIVE_DETECTOR = write(self.root / 'Read_Paste_Fiducial_Vision.js', {'fixture': 'native detector'})
        self.profile, self.sidecar, self.registration = fixture(self.root)
        self.reg_path = write(self.root / 'candidate.json', self.registration)
        self.profile_path = write(self.root / 'profile.json', self.profile)
        self.sidecar_path = write(self.root / 'sidecar.json', self.sidecar)

    def tearDown(self):
        self.tmp.cleanup()

    def prepare(self, name='preview'):
        return mod.prepare(self.reg_path, self.profile_path, self.sidecar_path, self.root / name)

    def test_stages_derived_fit_preserving_identity_and_offset(self):
        original_profile = self.profile_path.read_bytes()
        original_sidecar = self.sidecar_path.read_bytes()
        manifest = self.prepare()
        staged = json.loads((self.root / 'preview/calibration-sidecar.json').read_text())
        self.assertEqual(staged['profileId'], self.sidecar['profileId'])
        self.assertEqual(staged['sessionId'], self.sidecar['sessionId'])
        self.assertEqual(staged['boardTouchReference'], self.sidecar['boardTouchReference'])
        self.assertTrue(all(s['provenance'] == mod.DERIVED for s in staged['alignmentSamples']))
        self.assertEqual([s['ref'] for s in staged['alignmentSamples']], list(mod.REFS))
        self.assertEqual(manifest['padTargetCount'], 80)
        self.assertFalse(manifest['ledgerOrProfileMutation'])
        self.assertFalse(manifest['physicalRegistrationClaimed'])
        self.assertEqual(self.profile_path.read_bytes(), original_profile)
        self.assertEqual(self.sidecar_path.read_bytes(), original_sidecar)

    def test_preserves_existing_board_touch_lineage(self):
        datum = {'operatorConfirmedBoardTouch': True, 'surfaceIdentity': 'demo PCB',
                 'assumption': 'single-point-flat-plane-approximation', 'rawZ': 59.0,
                 'evidence': {'path': '/retained/touch.json', 'sha256': 'd' * 64}}
        self.sidecar['boardTouchReference'] = datum
        self.sidecar['zApplied'] = True
        write(self.sidecar_path, self.sidecar)
        self.prepare('touch-preview')
        staged = json.loads((self.root / 'touch-preview/calibration-sidecar.json').read_text())
        self.assertEqual(staged['boardTouchReference'], datum)
        self.assertTrue(staged['zApplied'])

    def test_accepts_only_reviewed_native_affine_with_heldouts(self):
        self.registration['scope'] = sorted(mod.NATIVE_AFFINE_SCOPES)[0]
        self.registration['independentHeldOutPadChecks'] = [
            {'padIdentityReviewed': True, 'centerMeasurementReviewed': True}]
        write(self.reg_path, self.registration)
        self.prepare('affine-preview')
        del self.registration['independentHeldOutPadChecks']
        write(self.reg_path, self.registration)
        with self.assertRaisesRegex(ValueError, 'held-out pad checks'):
            self.prepare('unreviewed-affine')

    def test_rejects_changed_inspection_job_hash(self):
        self.profile['sourceEvidence'][-1]['sha256'] = 'e' * 64
        write(self.profile_path, self.profile)
        with self.assertRaisesRegex(ValueError, 'profile-bound hash'):
            self.prepare('changed-inspection-job')

    def test_rejects_enabled_inspection_placement(self):
        job = ET.parse(self.profile['inspectionJob']).getroot()
        board_path = job.find(".//object[@class='org.openpnp.model.BoardLocation']").get('file-name')
        board = ET.parse(board_path)
        board.getroot().find("./placements/placement[@id='R1']").set('enabled', 'true')
        board.write(board_path, encoding='utf-8', xml_declaration=True)
        with self.assertRaisesRegex(ValueError, 'remain disabled'):
            self.prepare('enabled-placement')

    def test_rejects_bad_registration_hash_and_session(self):
        self.registration['board']['sha256'] = '0' * 64
        write(self.reg_path, self.registration)
        with self.assertRaisesRegex(ValueError, 'source hash changed'):
            self.prepare('bad-hash')
        self.registration['board']['sha256'] = sha(Path(self.registration['board']['path']))
        self.registration['session']['jvmStartMs'] += 1
        write(self.reg_path, self.registration)
        with self.assertRaisesRegex(ValueError, 'identity must match'):
            self.prepare('bad-session')

    def test_rejects_incomplete_coverage_and_nonaffine_fit(self):
        self.registration['resistorPadMachineXYTargets'].pop()
        write(self.reg_path, self.registration)
        with self.assertRaisesRegex(ValueError, 'exactly 80'):
            self.prepare('missing-target')
        self.registration['resistorPadMachineXYTargets'].append(
            {'padId': 'R40.2', 'machineXYMm': [499.0, 499.0]})
        write(self.reg_path, self.registration)
        with self.assertRaises(Exception):
            self.prepare('bad-fit')


if __name__ == '__main__':
    unittest.main()
