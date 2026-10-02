import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCOPE = 'contiguous-native-scrap-sequence-comparison'
PREVIEW = SCOPE + '-preview'


class SequenceScopeContractTests(unittest.TestCase):
    def read(self, path):
        return (ROOT / path).read_text()

    def test_scope_is_consistent_from_author_preparer_runner_and_finalizer(self):
        author = self.read('automation/paste/author-pressure-stabilization-sequence.py')
        preparer = self.read('automation/paste/prepare-contiguous-batch.py')
        runner = self.read('automation/paste/run-prepared-contiguous-batch.py')
        self.assertIn("'targetSurface': 'scrap-sequence-comparison'", author)
        self.assertIn("'sequenceProtocol': 'three-12-degree-sacrificial-then-three-6-degree-test-r2'", author)
        self.assertIn("scope='" + PREVIEW + "'", preparer)
        self.assertIn(PREVIEW, preparer[preparer.index('PREVIEW_SCOPES ='):preparer.index('\n\n', preparer.index('PREVIEW_SCOPES ='))])
        self.assertIn(PREVIEW, runner)
        self.assertIn(PREVIEW, self.read('automation/paste/test_finalize_contiguous_batch.py'))

    def test_detached_formatter_and_live_commissioner_validate_exact_scope_without_downgrade(self):
        preview = self.read('automation/scripts/Preview_Paste_Contiguous_Batch.js')
        commission = self.read('automation/scripts/Commission_Paste_Contiguous_Batch.js')
        policy = self.read('automation/paste/commissioning-stroke.cjs')
        self.assertIn("'" + PREVIEW + "'", preview)
        self.assertIn('CommissioningStroke.validateBatch(q,now,jvm,true)', preview)
        self.assertIn('noControllerAccess:true,noMotion:true', preview)
        self.assertIn("q.scope==='" + SCOPE + "'?'" + PREVIEW + "'", commission)
        self.assertIn("q.scope==='" + SCOPE + "'&&(nativePreviewRecord.request.targetSurface!==q.targetSurface||nativePreviewRecord.request.sequenceProtocol!==q.sequenceProtocol)", commission)
        self.assertIn("q.scope===(preview?'" + PREVIEW + "':'" + SCOPE + "')", policy)
        self.assertIn("q.targetSurface!=='scrap-sequence-comparison'", policy)
        self.assertIn("q.sequenceProtocol!=='three-12-degree-sacrificial-then-three-6-degree-test-r2'", policy)


if __name__ == '__main__':
    unittest.main()
