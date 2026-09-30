import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'scripts/capture_usb_overview.py'
spec = importlib.util.spec_from_file_location('overview', PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class OverviewCaptureTests(unittest.TestCase):
    def test_capture_is_exact_device_fullhd_mjpeg_twelfth_frame_only(self):
        command = m.capture_command('/synthetic')
        self.assertEqual(command[0], m.GST)
        self.assertIn('device=' + str(m.DEVICE), command)
        self.assertIn('num-buffers=12', command)
        self.assertIn('image/jpeg,width=1920,height=1080,framerate=30/1', command)
        self.assertIn('location=/synthetic/frame-%02d.jpg', command)
        self.assertIn('next-file=buffer', command)
        self.assertNotIn('jpegenc', command)
        self.assertNotIn('sh', command)

    def test_exact_preview_and_only_overview_device_required(self):
        env = {'DISPLAY': 'observed', 'XAUTHORITY': '/observed/auth', 'OTHER': 'not-copied'}
        self.assertEqual(m.validate_preview(m.GST, m.PREVIEW, env, {'/dev/video8'}, '/dev/video8'),
                         {k: env[k] for k in ('DISPLAY', 'XAUTHORITY')})
        for exe, argv, held, environment in [
            ('/usr/bin/other', m.PREVIEW, {'/dev/video8'}, env),
            (m.GST, m.PREVIEW + ['unexpected'], {'/dev/video8'}, env),
            (m.GST, m.PREVIEW, {'/dev/video8', '/dev/video0'}, env),
            (m.GST, m.PREVIEW, {'/dev/video2'}, env),
            (m.GST, m.PREVIEW, {'/dev/video8'}, {'DISPLAY': 'observed'})]:
            with self.assertRaises(ValueError):
                m.validate_preview(exe, argv, environment, held, '/dev/video8')

    def test_existing_output_refused_before_any_process_interface(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'existing.jpg';output.write_bytes(b'existing')
            with patch.object(m.os, 'pidfd_open') as opened:
                with self.assertRaises(ValueError):m.execute(123, output)
                opened.assert_not_called()
            self.assertEqual(output.read_bytes(), b'existing')

    def test_capture_failure_still_restores_known_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(m.os, 'pidfd_open', return_value=99), patch.object(m.os, 'close'), \
                 patch.object(m, 'inspect_preview', return_value=({'DISPLAY': 'x', 'XAUTHORITY': 'y'}, '/dev/video8')), \
                 patch.object(m.signal, 'pidfd_send_signal') as stop, \
                 patch.object(m.select, 'select', return_value=([99], [], [])), \
                 patch.object(m, 'owners', return_value=set()), \
                 patch.object(m.subprocess, 'run', side_effect=RuntimeError('capture failed')), \
                 patch.object(m, 'restore_preview', return_value=456) as restore:
                report=m.execute(123, Path(directory)/'new.jpg')
                stop.assert_called_once_with(99, m.signal.SIGTERM)
                restore.assert_called_once_with({'DISPLAY': 'x', 'XAUTHORITY': 'y'}, '/dev/video8')
                self.assertFalse(report['captureSaved']);self.assertTrue(report['previewRestored'])
                self.assertIn('capture failed', report['error'])


if __name__ == '__main__':unittest.main()
