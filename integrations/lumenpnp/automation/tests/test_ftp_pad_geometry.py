import copy
import importlib.util
import math
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'paste/pads/extract_ftp_pads.py'
spec = importlib.util.spec_from_file_location('ftp_pads', SOURCE)
p = importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
PCB = Path('/home/lumen/lumenpnp/pnp/pcb/ftp/ftp.kicad_pcb')
GERBER = Path('/home/lumen/paste-automation/test/ftp-F_Paste.gbr')


@unittest.skipUnless(PCB.is_file() and GERBER.is_file(), 'Requires actual canonical FTP board and pinned fork Gerber')
class FTPPadGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.board_text = PCB.read_text();cls.gerber_text = GERBER.read_text()
        cls.pads = p.extract_kicad(cls.board_text);cls.flashes = p.extract_gerber(cls.gerber_text)

    def test_all_actual_resistor_pads_crossmatch_complete_roundrect_geometry(self):
        pads = copy.deepcopy(self.pads)
        self.assertLess(p.crosscheck(pads, self.flashes), 0.000000134)
        self.assertEqual(len(pads), 80)
        self.assertEqual({x['reference'] for x in pads}, {f'R{i}' for i in range(1, 41)})
        for pad in pads:
            self.assertEqual(pad['sizeMm'], [0.8, 0.95])
            self.assertEqual(pad['cornerRadiusMm'], 0.2)
            self.assertAlmostEqual(pad['areaMm2'], 0.76-(4-math.pi)*0.04)
        for ref in p.REFERENCES:
            pair = [x for x in pads if x['reference'] == ref]
            self.assertAlmostEqual(p.distance(pair[0]['centerMm'], pair[1]['centerMm']), 1.65)

    def test_absolute_pad_angle_and_rotated_relative_centers(self):
        by_id = {x['id']: x for x in self.pads}
        expected = {'R2.1': (40.416603, 40.416624), 'R2.2': (41.583329, 41.583350),
                    'R1.1': (37.499966, 41.674987), 'R1.2': (37.499966, 43.324987)}
        for name, xy in expected.items():
            self.assertLess(p.distance(by_id[name]['centerMm'], xy), 0.000001)
        self.assertEqual(by_id['R2.1']['rotationDeg'], 45)
        self.assertEqual({x['rotationDeg'] % 360 for x in self.pads}, {0, 45, 90, 135, 180, 315, 270, 225})

    def test_position_shape_identity_and_duplicate_flash_mismatches_rejected(self):
        target = next(i for i,f in enumerate(self.flashes) if f['reference'] == 'R16')
        for change in ('center', 'radius', 'corner', 'reference', 'duplicate'):
            flashes = copy.deepcopy(self.flashes)
            if change == 'center':flashes[target]['center'] = (99,99)
            elif change == 'radius':flashes[target]['radius'] += 0.01
            elif change == 'corner':flashes[target]['corners'][0] = (0,0)
            elif change == 'reference':flashes[target]['reference'] = 'R17'
            else:flashes.append(copy.deepcopy(flashes[target]))
            with self.subTest(change=change), self.assertRaises(ValueError):p.crosscheck(copy.deepcopy(self.pads), flashes)

    def test_unsupported_gerber_units_polarity_macro_or_draw_are_rejected(self):
        for old,new in [('%MOMM*%','%MOIN*%'),('%FSLAX46Y46*%','%FSLIX46Y46*%'),
                        ('%LPD*%','%LPC*%'),('FilePolarity,Positive','FilePolarity,Negative'),
                        ('1,1,$1+$1,$2,$3*','1,0,$1+$1,$2,$3*'),('D03*','D01*')]:
            with self.subTest(new=new),self.assertRaises(ValueError):p.extract_gerber(self.gerber_text.replace(old,new,1))

    def test_no_silent_paste_override_or_missing_reference(self):
        for mutated in [self.board_text.replace('(setup','(setup (pad_to_paste_clearance 0.1)',1),
                        self.board_text.replace('(property "Reference" "R16"','(property "Reference" "R99"',1),
                        self.board_text.replace('(footprint "Resistor_SMD:R_0603_1608Metric"','(footprint "Resistor_SMD:Unknown"',1)]:
            with self.assertRaises(ValueError):p.extract_kicad(mutated)

    def test_plan_has_provenance_but_no_executable_or_calibrated_targets(self):
        plan = p.build(PCB, GERBER)
        self.assertFalse(plan['executionReady']);self.assertEqual(plan['pastePadCount'], 80)
        self.assertTrue(all(v is None for v in plan['pending'].values()))
        for target in plan['candidateDeposits']:
            for key in ('machineXYMm','surfaceZMm','standoffMm','doseDegrees'):self.assertIsNone(target[key])
        self.assertTrue(all(len(s['sha256']) == 64 for s in plan['sources']))
        self.assertEqual(plan, p.build(PCB, GERBER))


class GerberProvenanceTests(unittest.TestCase):
    def test_pinned_head_alone_does_not_accept_dirty_gerber(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary);(root/'test').mkdir();gerber = root/'test/ftp-F_Paste.gbr'
            gerber.write_bytes(b'actual-file')
            with patch.object(p.subprocess, 'check_output', side_effect=[p.PINNED_FORK+'\n',str(root)+'\n',b'actual-file']):
                self.assertEqual(p.verify_pinned_gerber(gerber)['commit'], p.PINNED_FORK)
            with patch.object(p.subprocess, 'check_output', side_effect=[p.PINNED_FORK+'\n',str(root)+'\n',b'different-pinned-blob']):
                with self.assertRaisesRegex(ValueError, 'differs from pinned'):p.verify_pinned_gerber(gerber)
            with patch.object(p.subprocess, 'check_output', return_value='different-head\n'):
                with self.assertRaisesRegex(ValueError, 'pinned audited'):p.verify_pinned_gerber(gerber)


if __name__ == '__main__':unittest.main()
