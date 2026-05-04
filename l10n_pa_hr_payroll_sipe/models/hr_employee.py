# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, fields, models
from odoo.exceptions import ValidationError

from ..lib.sipe_writer import (
    SIPE_TIPO_CEDULA,
    SIPE_TIPO_PASAPORTE,
    SIPE_TIPO_SEGURO_SOCIAL,
)

SIPE_ID_TYPE_SELECTION = [
    (SIPE_TIPO_CEDULA, "Cédula"),
    (SIPE_TIPO_PASAPORTE, "Pasaporte"),
    (SIPE_TIPO_SEGURO_SOCIAL, "Seguro Social"),
]


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    l10n_pa_sipe_id_type = fields.Selection(
        selection=SIPE_ID_TYPE_SELECTION,
        string="SIPE Tipo de Documento",
        default=SIPE_TIPO_CEDULA,
        help=(
            "The CSS SIPE planilla file requires one of three identification "
            "types per employee. Defaults to Cédula for Panama nationals; use "
            "Pasaporte for foreign employees and Seguro Social only when the "
            "employee has a CSS-only number with no civil document."
        ),
    )
    l10n_pa_css_number = fields.Char(
        string="Número de Seguro Social (CSS)",
        help=(
            "CSS Seguro Social number assigned to the employee. Required for "
            "the SIPE planilla bulk upload. Distinct from the employee's "
            "civil identification number (cédula or pasaporte)."
        ),
    )

    def _l10n_pa_sipe_split_name(self):
        """Return (nombre, apellido) for the SIPE row.

        Uses `legal_name` if populated, otherwise falls back to `name`. The
        split rule mirrors the conventional Panama practice of keeping all
        given names in `nombre` and all surnames in `apellido`. Single-token
        names go entirely into `nombre` with `apellido` left as an empty
        string sentinel that the wizard later replaces with a hyphen so the
        SIPE row passes the non-empty check.
        """
        self.ensure_one()
        full = (self.legal_name or self.name or "").strip()
        if not full:
            raise ValidationError(_("Employee %s has no name set.", self.id))
        # Heuristic: half the tokens are given names, half are surnames.
        # Operators with structured first/last name fields should override
        # this method. Most Odoo deployments only have `name`.
        tokens = full.split()
        if len(tokens) == 1:
            return tokens[0], "-"
        mid = len(tokens) // 2
        return " ".join(tokens[:mid]), " ".join(tokens[mid:])
