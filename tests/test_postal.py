"""Pure-Python checks for Panama postal-code helpers."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "l10n_pa_postal" / "lib"))

from postal import decode, encode, validate


class TestPanamaPostalCodec(unittest.TestCase):
    def test_decode_full_code(self):
        decoded = decode("ACC99-PJ42W")

        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.estafeta_prefix, "AC")
        self.assertEqual(decoded.body, "C99PJ42W")
        self.assertEqual(decoded.level, "PICO")
        self.assertEqual(decoded.precision_meters, 3.3)
        self.assertAlmostEqual(decoded.lat, 8.94444609375)
        self.assertAlmostEqual(decoded.lng, -79.56167109375)

    def test_decode_partial_macro_code(self):
        decoded = decode("C9")

        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.level, "MACRO")
        self.assertAlmostEqual(decoded.lat, 9.07375)
        self.assertAlmostEqual(decoded.lng, -79.58125)

    def test_validate_rejects_ambiguous_letters(self):
        self.assertFalse(validate("ACIC99-PJ42W"))

    def test_encode_returns_geospatial_body(self):
        self.assertEqual(encode(8.94444609375, -79.56167109375), "C99-PJ42W")


if __name__ == "__main__":
    unittest.main()
