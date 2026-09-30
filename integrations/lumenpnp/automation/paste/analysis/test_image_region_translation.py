import io
import unittest
from PIL import Image, ImageDraw
from image_region_translation import match


def png(image):
    b = io.BytesIO(); image.save(b, format='PNG'); return b.getvalue()


class RegionMatchTests(unittest.TestCase):
    def test_opposite_regions_and_stationary_reference(self):
        a = Image.new('L', (140, 100)); b = a.copy()
        for image, shifts in [(a, (0, 0, 0)), (b, (-3, 2, 0))]:
            d = ImageDraw.Draw(image)
            for x, dy in zip((25, 65, 105), shifts):
                d.rectangle((x, 35+dy, x+7, 55+dy), fill=210)
                d.rectangle((x+5, 40+dy, x+13, 45+dy), fill=120)
        r = match(png(a), png(b), {str(x): [x-4, 29, x+18, 63] for x in (25, 65, 105)})
        self.assertEqual([v['best']['dyPx'] for v in r['regions'].values()], [-3, 2, 0])
        self.assertTrue(all(v['best']['dxPx'] == 0 for v in r['regions'].values()))

    def test_no_padding_or_bad_search(self):
        data = png(Image.new('L', (20, 20)))
        for roi in ([0, 0, 10, 10], [5, 5, 5, 10], [5.0, 5, 10, 10]):
            with self.assertRaises(ValueError): match(data, data, {'bad': roi})
        with self.assertRaises(ValueError): match(data, data, {'bad': [5, 7, 10, 12]}, 0)
