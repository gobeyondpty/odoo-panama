# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Panama partner extensions: identification types and Dígito Verificador.

The DV (Dígito Verificador) algorithm is ported from the public reference
implementation `apple314159/panama-dv` (Apache-2.0), which itself
documents the spec from ANIP/DGI's `DV_RUC.pdf`. This file re-implements
the same algorithm in Python for Odoo without taking a runtime
dependency on the upstream package.
"""
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


# Lookup table used by the DGI cross-reference step for legacy juridical
# RUC formats (third digit < 5 and chars 4-5 are zero). Maps two-digit
# codes to substitute values per ANIP DV_RUC.pdf.
_DV_LEGACY_LOOKUP = {
    '00': '00', '10': '01', '11': '02', '12': '03', '13': '04',
    '14': '05', '15': '06', '16': '07', '17': '08', '18': '09',
    '19': '01', '20': '02', '21': '03', '22': '04', '23': '07',
    '24': '08', '25': '09', '26': '02', '27': '03', '28': '04',
    '29': '05', '30': '06', '31': '07', '32': '08', '33': '09',
    '34': '01', '35': '02', '36': '03', '37': '04', '38': '05',
    '39': '06', '40': '07', '41': '08', '42': '09', '43': '01',
    '44': '02', '45': '03', '46': '04', '47': '05', '48': '06',
    '49': '07',
}

# Identification types whose DV can be algorithmically computed.
_DV_COMPUTABLE_ID_TYPES = ('ruc', 'cedula', 'nt', 'extranjero', 'pi', 'av')

# Module-prefixed external IDs of identification types (as loaded from
# data/l10n_latam.identification.type.csv).
_ID_TYPE_REF = {
    code: f'l10n_pa.{code}'
    for code in ('ruc', 'cedula', 'pasaporte', 'nt', 'extranjero', 'pi', 'av')
}


def _digit_dv(sw, ructb):
    """Compute one DV digit from a normalized RUC string.

    Walks the digits right-to-left, multiplying each by an increasing
    weight starting at 2; if `sw` (legacy juridical flag) is set, the
    weight 12 is skipped. Returns 0 when remainder ∈ {0, 1}, else 11-r.
    """
    j = 2
    nsuma = 0
    for c in reversed(ructb):
        if sw and j == 12:
            sw = False
            j -= 1
        nsuma += j * (ord(c) - ord('0'))
        j += 1
    r = nsuma % 11
    if r > 1:
        return 11 - r
    return 0


def calculate_dv(ruc):
    """Compute the two-digit Dígito Verificador for a Panama RUC string.

    Accepts the dash-separated formats documented by ANIP:

    * Cédula:               ``8-442-445``
    * PE / N:               ``PE-10-442``, ``N-45-832``
    * E:                    ``E-12-342``
    * AV / PI:              ``1AV-432-658``, ``4PI-234-123``
    * RUC jurídico:         ``11947-1027-0229562``, ``11947-1-0229562``
    * RUC NT:               ``<n>-NT-<m>-<k>``

    Returns a 2-character string ``"<DV1><DV2>"`` (e.g. ``"08"``), or
    the empty string for inputs that cannot be DV-computed (passport,
    malformed, foreign IDs without a valid template).
    """
    if not ruc:
        return ''
    rs = ruc.split('-')
    # Guard the length envelope: 3..5 segments, with 4 segments only
    # legal for the NT format.
    if (len(rs) == 4 and rs[1] != 'NT') or len(rs) < 3 or len(rs) > 5:
        return ''

    sw = False

    if ruc[0] == 'E':
        ructb = ('0' * (4 - len(rs[1])) + '0000005' + '00' + '50'
                 + '0' * (3 - len(rs[1])) + rs[1]
                 + '0' * (5 - len(rs[2])) + rs[2])
    elif rs[1] == 'NT':
        ructb = ('0' * (4 - len(rs[1])) + '0000005'
                 + '00' * (2 - len(rs[0][:-2])) + rs[0][:-2] + '43'
                 + '0' * (3 - len(rs[2])) + rs[2]
                 + '0' * (5 - len(rs[3])) + rs[3])
    elif rs[0][-2:] == 'AV':
        ructb = ('0' * (4 - len(rs[1])) + '0000005'
                 + '00' * (2 - len(rs[0][:-2])) + rs[0][:-2] + '15'
                 + '0' * (3 - len(rs[1])) + rs[1]
                 + '0' * (5 - len(rs[2])) + rs[2])
    elif rs[0][-2:] == 'PI':
        ructb = ('0' * (4 - len(rs[1])) + '0000005'
                 + '00' * (2 - len(rs[0][:-2])) + rs[0][:-2] + '79'
                 + '0' * (3 - len(rs[1])) + rs[1]
                 + '0' * (5 - len(rs[2])) + rs[2])
    elif rs[0] == 'PE':
        ructb = ('0' * (4 - len(rs[1])) + '0000005' + '00' + '75'
                 + '0' * (3 - len(rs[1])) + rs[1]
                 + '0' * (5 - len(rs[2])) + rs[2])
    elif ruc[0] == 'N':
        ructb = ('0' * (4 - len(rs[1])) + '0000005' + '00' + '40'
                 + '0' * (3 - len(rs[1])) + rs[1]
                 + '0' * (5 - len(rs[2])) + rs[2])
    elif 0 < len(rs[0]) <= 2:
        # Short numeric prefix: cédula format (e.g. "8-442-445").
        ructb = ('0' * (4 - len(rs[1])) + '0000005'
                 + '0' * (2 - len(rs[0])) + rs[0] + '00'
                 + '0' * (3 - len(rs[1])) + rs[1]
                 + '0' * (5 - len(rs[2])) + rs[2])
    else:
        # Juridical RUC: <=10-digit tomo, <=4-digit folio, asiento variable
        # (typically 6 but may exceed). The original algorithm tolerates
        # negative-length zero-padding (yielding '') so we mirror that.
        if not (rs[0] + rs[1] + rs[2]).isdigit():
            return ''
        ructb = ('0' * max(0, 10 - len(rs[0])) + rs[0]
                 + '0' * max(0, 4 - len(rs[1])) + rs[1]
                 + '0' * max(0, 6 - len(rs[2])) + rs[2])
        # Legacy flag: pre-2005 jurídicos with positions 4-5 = "00" and
        # position 6 < "5" require the cross-reference table.
        sw = ructb[3] == '0' and ructb[4] == '0' and ructb[5] < '5'

    if not all(c.isdigit() for c in ructb):
        return ''

    if sw:
        ructb = ructb[:5] + _DV_LEGACY_LOOKUP.get(ructb[5:7], ructb[5:7]) + ructb[7:]

    dv1 = _digit_dv(sw, ructb)
    dv2 = _digit_dv(sw, ructb + chr(48 + dv1))
    return chr(48 + dv1) + chr(48 + dv2)


# Validation regex per identification type. Passport is a permissive
# alphanumeric pattern; the others are anchored to the DGI templates.
_ID_FORMAT_REGEX = {
    'ruc': re.compile(
        r'^('
        r'\d{1,2}-\d{1,4}-\d{1,5}'                 # cédula natural
        r'|PE-\d{1,4}-\d{1,5}'
        r'|N-\d{1,4}-\d{1,5}'
        r'|E-\d{1,4}-\d{1,5}'
        r'|\d?AV-\d{1,4}-\d{1,5}'
        r'|\d?PI-\d{1,4}-\d{1,5}'
        r'|\d+-\d+-\d+'                            # juridical RUC (also matches cédula)
        r'|\d+-NT-\d+-\d+'                         # juridical NT
        r')$'
    ),
    'cedula': re.compile(r'^\d{1,2}-\d{1,4}-\d{1,5}$'),
    'pasaporte': re.compile(r'^[A-Z0-9]{5,20}$'),
    'nt': re.compile(r'^\d{1,10}-NT-\d{1,4}-\d{1,6}$'),
    'extranjero': re.compile(r'^E-\d{1,4}-\d{1,5}$'),
    'pi': re.compile(r'^\d?PI-\d{1,4}-\d{1,5}$'),
    'av': re.compile(r'^\d?AV-\d{1,4}-\d{1,5}$'),
}


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_pa_dv = fields.Char(
        string="Dígito Verificador",
        compute='_compute_l10n_pa_dv',
        store=True,
        copy=False,
        help="Dígito Verificador (DV) calculated for the Panama RUC or "
             "cédula identifier. Empty when the identifier cannot be "
             "DV-computed (e.g., passport).",
    )

    @api.depends('vat', 'l10n_latam_identification_type_id', 'country_id')
    def _compute_l10n_pa_dv(self):
        """Recompute DV whenever the partner's tax ID/identification type/country changes."""
        for partner in self:
            partner.l10n_pa_dv = partner._l10n_pa_compute_dv() or False

    def _l10n_pa_compute_dv(self):
        """Return the 2-character DV string for this partner, or empty."""
        self.ensure_one()
        id_code = self._l10n_pa_id_type_code()
        if id_code not in _DV_COMPUTABLE_ID_TYPES:
            return ''
        if not self.vat:
            return ''
        return calculate_dv(self.vat.strip())

    def _l10n_pa_id_type_code(self):
        """Return the short code of the identification type ('ruc', 'cedula', ...)
        if the partner uses a Panama identification type, otherwise empty.
        """
        self.ensure_one()
        id_type = self.l10n_latam_identification_type_id
        if not id_type:
            return ''
        # Resolve via external ID lookup. Returns '' if the partner uses
        # a non-Panama identification type.
        for code, xml_id in _ID_TYPE_REF.items():
            ref = self.env.ref(xml_id, raise_if_not_found=False)
            if ref and ref.id == id_type.id:
                return code
        return ''

    def _l10n_pa_format_valid(self):
        """Validate the format of the partner's Panama identifier."""
        self.ensure_one()
        id_code = self._l10n_pa_id_type_code()
        if not id_code or not self.vat:
            return True
        regex = _ID_FORMAT_REGEX.get(id_code)
        if not regex:
            return True
        return bool(regex.match(self.vat.strip()))

    @api.constrains('vat', 'l10n_latam_identification_type_id', 'country_id')
    def _check_l10n_pa_ruc_format(self):
        """Reject malformed Panama identifiers at write time."""
        for partner in self:
            if partner.country_id and partner.country_id.code != 'PA':
                continue
            if (
                partner._l10n_pa_id_type_code()
                and partner.vat
                and not partner._l10n_pa_format_valid()
            ):
                raise ValidationError(_(
                    "El formato de la identificación '%(vat)s' no es válido "
                    "para el tipo de identificación seleccionado.",
                    vat=partner.vat,
                ))

    def _run_check_identification(self, validation='error'):
        """Hook into l10n_latam_base's identification check."""
        for partner in self:
            if not partner.vat or not partner._l10n_pa_id_type_code():
                continue
            if not partner._l10n_pa_format_valid():
                if validation == 'error':
                    raise ValidationError(_(
                        "El formato de la identificación '%(vat)s' no es válido.",
                        vat=partner.vat,
                    ))
                _logger.warning("Invalid Panama identifier format: %s", partner.vat)
        return super()._run_check_identification(validation=validation)
