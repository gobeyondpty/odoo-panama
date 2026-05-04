# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Tests for the Panama Dígito Verificador algorithm.

Test vectors come from:

* `apple314159/panama-dv` (Apache-2.0) — `ructest.py` test cases
* ANIP DV_RUC.pdf — formal spec describing the algorithm
"""
from odoo.tests.common import BaseCase, tagged

from odoo.addons.l10n_pa.models.res_partner import calculate_dv


@tagged('-at_install', 'post_install', 'l10n_pa')
class TestDigitoVerificador(BaseCase):
    """Pure-function tests; no DB access required."""

    def test_cedula_natural_persons(self):
        """Cédulas (Personas Naturales) per ANIP Formato I."""
        self.assertEqual(calculate_dv('8-442-445'), '08')
        self.assertEqual(calculate_dv('PE-10-442'), '50')
        self.assertEqual(calculate_dv('N-45-832'), '58')
        self.assertEqual(calculate_dv('E-12-342'), '10')
        self.assertEqual(calculate_dv('1AV-432-658'), '96')
        self.assertEqual(calculate_dv('4PI-234-123'), '96')

    def test_ruc_juridicas(self):
        """RUC para Persona Jurídica per ANIP Formato III."""
        self.assertEqual(calculate_dv('11947-1027-0229562'), '71')
        self.assertEqual(calculate_dv('11947-1-0229562'), '42')

    def test_legacy_juridico_cross_reference(self):
        """Pre-2005 jurídicos hit the cross-reference lookup table."""
        self.assertEqual(calculate_dv('61302-14-123411'), '22')
        self.assertEqual(calculate_dv('1102-85-117211'), '95')
        self.assertEqual(calculate_dv('2486589-1-816994'), '62')
        self.assertEqual(calculate_dv('1830234-1-710357'), '82')
        self.assertEqual(calculate_dv('41369-85-283456'), '73')

    def test_remainder_zero_yields_zero(self):
        """Remainder 0 path returns '00' (not 11)."""
        self.assertEqual(calculate_dv('64296-75-357434'), '00')

    def test_short_juridico_codes(self):
        """Numeric prefixes that don't trigger legacy reference."""
        self.assertEqual(calculate_dv('203141-1-17214'), '60')
        self.assertEqual(calculate_dv('1075137-1-553125'), '18')

    def test_invalid_inputs(self):
        """Empty string, single token, alphanumeric passport — all return ''."""
        self.assertEqual(calculate_dv(''), '')
        self.assertEqual(calculate_dv('E'), '')
        self.assertEqual(calculate_dv('PAS1311723564'), '')

    def test_unknown_prefix_returns_empty(self):
        """A non-digit prefix that isn't one of the documented codes
        cannot be DV-computed."""
        self.assertEqual(calculate_dv('XYZ-1-1'), '')

    def test_leading_zeros_in_segments(self):
        """Segments with leading zeros pad correctly (asiento boundary)."""
        # Same RUC as 11947-1-0229562 should produce same DV regardless of
        # the asiento having a leading zero (it does in this case).
        self.assertEqual(calculate_dv('11947-1-0229562'), '42')

    def test_dv_is_two_chars(self):
        """Successful DV computation always yields exactly 2 chars."""
        for ruc in ('8-442-445', '11947-1-0229562', '64296-75-357434'):
            dv = calculate_dv(ruc)
            self.assertEqual(len(dv), 2, f"DV for {ruc!r} should be 2 chars, got {dv!r}")
            self.assertTrue(dv.isdigit(), f"DV for {ruc!r} should be digits, got {dv!r}")
