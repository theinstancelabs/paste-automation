import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT=Path(__file__).with_name('prepare-contiguous-batch.py')
SPEC=importlib.util.spec_from_file_location('prepare_contiguous_batch',SCRIPT)
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)

class SelectedFinalizeTests(unittest.TestCase):
    def test_selected_pad_native_preview_finalizes_with_preserved_scope(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);formatter=root/'stage.txt';formatter.write_text('G1 Z53.4 F...\n')
            fe=M.evidence(formatter);raw={'X':1.0,'Y':2.0,'Z':58.4,'A':720.0,'B':-1000.0};target={**raw,'Z':53.4}
            q={'scope':'contiguous-native-ftp-selected-pads-preview','enabled':False,'id':'12345678-1234-1234-1234-123456789abc','jvmStartMs':10,'liveConfigurationSha256':'a'*64,'previewStages':[{'axis':'Z','speedFraction':1.0,'startRaw':raw,'targetRaw':target}],'evidence':[]}
            request=root/'preview-request.json';request.write_text(json.dumps(q))
            stage={'axis':'Z','speedFraction':1.0,'startRaw':raw,'targetRaw':target,'formatterEvidence':fe,'path':fe['path'],'sha256':fe['sha256'],'expandedCommands':['G1 Z53.4 F...']}
            report={'status':'completed-model-only-contiguous-batch-preview','noControllerAccess':True,'noMotion':True,'id':q['id'],'jvmStartMs':10,'liveConfigurationSha256':'a'*64,'request':q,'stages':[stage]}
            preview=root/'report.json';preview.write_text(json.dumps(report))
            with patch.object(M,'node_validate'):
                M.finalize(SimpleNamespace(request=str(request),preview=str(preview)))
            runtime=json.loads((root/'runtime-request.json').read_text())
            self.assertEqual(runtime['scope'],'contiguous-native-ftp-selected-pads')
            self.assertEqual(runtime['previewStages'][0]['expandedCommands'],stage['expandedCommands'])
            self.assertFalse(runtime['enabled'])

    def test_scrap_sequence_native_preview_finalizes_without_scope_downgrade(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);formatter=root/'stage.txt';formatter.write_text('G1 Z53.45 F...\n')
            fe=M.evidence(formatter);raw={'X':1.0,'Y':2.0,'Z':58.45,'A':720.0,'B':-3266.0};target={**raw,'Z':53.45}
            q={'scope':'contiguous-native-scrap-sequence-comparison-preview','targetSurface':'scrap-sequence-comparison','sequenceProtocol':'three-12-degree-sacrificial-then-three-6-degree-test-r2','enabled':False,'id':'22345678-1234-1234-1234-123456789abc','jvmStartMs':10,'liveConfigurationSha256':'a'*64,'previewStages':[{'axis':'Z','speedFraction':1.0,'startRaw':raw,'targetRaw':target}],'evidence':[]}
            request=root/'preview-request.json';request.write_text(json.dumps(q))
            stage={'axis':'Z','speedFraction':1.0,'startRaw':raw,'targetRaw':target,'formatterEvidence':fe,'path':fe['path'],'sha256':fe['sha256'],'expandedCommands':['G1 Z53.45 F...']}
            report={'status':'completed-model-only-contiguous-batch-preview','noControllerAccess':True,'noMotion':True,'id':q['id'],'jvmStartMs':10,'liveConfigurationSha256':'a'*64,'request':q,'stages':[stage]}
            preview=root/'report.json';preview.write_text(json.dumps(report))
            with patch.object(M,'node_validate'):
                M.finalize(SimpleNamespace(request=str(request),preview=str(preview)))
            runtime=json.loads((root/'runtime-request.json').read_text())
            self.assertEqual(runtime['scope'],'contiguous-native-scrap-sequence-comparison')
            self.assertEqual(runtime['targetSurface'],'scrap-sequence-comparison')
            self.assertEqual(runtime['sequenceProtocol'],q['sequenceProtocol'])
            self.assertFalse(runtime['enabled'])

if __name__=='__main__':unittest.main()
