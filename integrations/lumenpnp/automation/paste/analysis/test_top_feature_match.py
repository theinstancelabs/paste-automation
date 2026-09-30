import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from top_feature_match import match


def frames(offset_x, offset_y):
    before = Image.new('RGB', (360, 240), (0, 20, 80))
    after = Image.new('RGB', (360, 240), (0, 20, 80))
    # Asymmetric, nonrepetitive synthetic marker; not machine evidence.
    draw = ImageDraw.Draw(before)
    draw.rectangle((65, 65, 82, 115), fill=(10, 210, 220))
    draw.rectangle((92, 80, 135, 91), fill=(10, 210, 220))
    draw.ellipse((112, 100, 130, 118), fill=(10, 210, 220))
    marker = before.crop((40, 40, 160, 140))
    after.paste(marker, (40 + offset_x, 40 + offset_y))
    return before, after


class FeatureMatchTests(unittest.TestCase):
    def run_frames(self, dx, dy, max_shift):
        with tempfile.TemporaryDirectory() as temp:
            before, after = frames(dx, dy)
            a, b = Path(temp) / 'a.png', Path(temp) / 'b.png'
            before.save(a)
            after.save(b)
            return match(a, b, (40, 40, 160, 140), max_shift)

    def test_finds_explicit_same_feature_translation(self):
        result = self.run_frames(90, -6, 140)
        self.assertEqual(result['medianTranslationPx'], {'x': 90, 'y': -6})
        self.assertEqual(result['thresholdSpreadPx']['x'], [90, 90])
        self.assertFalse(any(x['touchesSearchBoundary'] for x in result['thresholdMatches']))

    def test_finds_negative_translation(self):
        result = self.run_frames(-25, 8, 40)
        self.assertLessEqual(abs(result['medianTranslationPx']['x'] + 25), 1)
        self.assertEqual(result['medianTranslationPx']['y'], 8)

    def test_rejects_winner_at_search_boundary(self):
        with self.assertRaisesRegex(ValueError, 'touches search boundary'):
            self.run_frames(130, 0, 120)

    def test_rejects_no_feature_contrast(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp) / 'a.png', Path(temp) / 'b.png'
            blank = Image.new('RGB', (360, 240), (0, 20, 80))
            blank.save(a)
            blank.save(b)
            with self.assertRaisesRegex(ValueError, 'insufficient.*contrast'):
                match(a, b, (40, 40, 160, 140), 120)


if __name__ == '__main__':
    unittest.main()
