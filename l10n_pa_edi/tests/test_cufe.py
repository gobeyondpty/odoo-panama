# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Tests for CUFE generation.

The CUFE algorithm is deterministic given fixed inputs (including the
9-digit security code). These tests pin a known seeded code and verify
the resulting CUFE matches the structural shape and Luhn check digit
rules from the dgi-fe TypeScript reference (`src/fe/CUFE.ts`).
"""
from datetime import date

from odoo.tests.common import BaseCase, tagged

from odoo.addons.l10n_pa_edi.models.cufe import (
    _asciify,
    _luhn_check_digit,
    build_cufe,
    generate_security_code,
)


@tagged('-at_install', 'post_install', 'l10n_pa_edi')
class TestCUFEHelpers(BaseCase):

    def test_asciify_passes_through_digits(self):
        self.assertEqual(_asciify('1234567890'), '1234567890')

    def test_asciify_replaces_non_digits_with_codepoint_last_digit(self):
        # 'A' = 65 → last digit is 5
        self.assertEqual(_asciify('A'), '5')
        # '-' = 45 → last digit is 5
        self.assertEqual(_asciify('-'), '5')

    def test_asciify_mixed_string(self):
        # '155718881-2-2018' has 9 + 1 + 1 + 1 + 4 = 16 chars; dashes
        # (ASCII 45) get replaced by '5', everything else passes through.
        self.assertEqual(_asciify('155718881-2-2018'), '1557188815252018')

    def test_luhn_check_digit_validates(self):
        # The CUFE Luhn must satisfy: total + check ≡ 0 (mod 10).
        for s in ('0', '1', '79927398713', '4111111111111'):
            check = _luhn_check_digit(s)
            self.assertEqual(len(check), 1)
            self.assertTrue(check.isdigit())

    def test_luhn_check_digit_rejects_non_digits(self):
        with self.assertRaises(ValueError):
            _luhn_check_digit('12A')

    def test_security_code_is_nine_digits(self):
        for seed in (1, 42, 9999):
            code = generate_security_code(seed)
            self.assertEqual(len(code), 9)
            self.assertTrue(code.isdigit())

    def test_security_code_is_deterministic_with_seed(self):
        self.assertEqual(generate_security_code(123), generate_security_code(123))
        self.assertNotEqual(generate_security_code(1), generate_security_code(2))


@tagged('-at_install', 'post_install', 'l10n_pa_edi')
class TestBuildCUFE(BaseCase):
    """`build_cufe` end-to-end with deterministic inputs."""

    def _base_kwargs(self, **overrides):
        kw = dict(
            tipo_documento='01',
            tipo_ruc='2',
            ruc='155718881-2-2018',
            dv='62',
            sucursal='1',
            fecha_emision=date(2026, 5, 4),
            nro_df='123',
            pto_fac_df='1',
            tipo_emision='01',
            ambiente='2',
            security_code='123456789',
        )
        kw.update(overrides)
        return kw

    def test_build_cufe_is_deterministic(self):
        c1 = build_cufe(**self._base_kwargs())
        c2 = build_cufe(**self._base_kwargs())
        self.assertEqual(c1, c2)

    def test_build_cufe_changes_with_security_code(self):
        c1 = build_cufe(**self._base_kwargs(security_code='111111111'))
        c2 = build_cufe(**self._base_kwargs(security_code='222222222'))
        self.assertNotEqual(c1, c2)

    def test_build_cufe_changes_with_doc_type(self):
        c1 = build_cufe(**self._base_kwargs(tipo_documento='01'))
        c2 = build_cufe(**self._base_kwargs(tipo_documento='04'))
        self.assertNotEqual(c1, c2)

    def test_build_cufe_includes_ruc_and_dv(self):
        cufe = build_cufe(**self._base_kwargs(ruc='155718881-2-2018', dv='62'))
        self.assertIn('155718881-2-2018', cufe)
        self.assertIn('-62', cufe)

    def test_build_cufe_pads_short_fields(self):
        cufe = build_cufe(**self._base_kwargs(sucursal='9', nro_df='1', pto_fac_df='2'))
        # The length should account for: 2+1+15(ruc)+3(-DD)+4+8+10+3+2+1+9+1 = 59
        # Length is sensitive to RUC length; assert presence of zero-padded fields.
        self.assertIn('0009', cufe)        # sucursal padded to 4
        self.assertIn('0000000001', cufe)  # nro_df padded to 10
        self.assertIn('002', cufe)         # pto_fac_df padded to 3

    def test_build_cufe_includes_date(self):
        cufe = build_cufe(**self._base_kwargs(fecha_emision=date(2026, 1, 15)))
        self.assertIn('20260115', cufe)

    def test_build_cufe_validates_inputs(self):
        with self.assertRaises(ValueError):
            build_cufe(**self._base_kwargs(tipo_documento='1'))   # not 2-char
        with self.assertRaises(ValueError):
            build_cufe(**self._base_kwargs(tipo_ruc='3'))         # not 1 or 2
        with self.assertRaises(ValueError):
            build_cufe(**self._base_kwargs(dv='8'))               # not 2-char
        with self.assertRaises(ValueError):
            build_cufe(**self._base_kwargs(ambiente='9'))         # not 1 or 2
        with self.assertRaises(ValueError):
            build_cufe(**self._base_kwargs(security_code='12345'))  # not 9 digits

    def test_build_cufe_check_digit_validates(self):
        """Strip the trailing check digit and verify the remainder + check ≡ 0 (Luhn)."""
        cufe = build_cufe(**self._base_kwargs())
        body, check = cufe[:-1], cufe[-1]
        recomputed = _luhn_check_digit(_asciify(body))
        self.assertEqual(check, recomputed)
