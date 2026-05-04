# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models

from ..lib.sipe_writer import COLUMN_FIELD_META

_METADATA_KEYS = frozenset((
    "tipo_documento",
    "numero_documento",
    "numero_seguro_social",
    "nombre",
    "apellido",
))
SIPE_COLUMN_SELECTION = [
    (key, f"{label} ({letter})")
    for letter, key, label in COLUMN_FIELD_META
    if key not in _METADATA_KEYS
]


class HrSalaryRule(models.Model):
    _inherit = "hr.salary.rule"

    l10n_pa_sipe_column = fields.Selection(
        selection=SIPE_COLUMN_SELECTION,
        string="SIPE Column",
        help=(
            "If set, the rule's amount on a posted payslip is summed into "
            "this column of the CSS SIPE bulk-upload XLSX. Leave empty for "
            "rules that should not flow to SIPE (e.g. internal accruals, "
            "employer-side contributions)."
        ),
    )
