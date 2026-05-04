from odoo import api, fields, models

from ..lib import calculations


class ResCompany(models.Model):
    """Company-scoped Panama payroll configuration.

    The CSS-assigned professional-risk grade (Decreto Gabinete 68/1970
    art. 51) is per-employer, so it lives on ``res.company`` rather than
    as a single global rule parameter. The grade × 0.07 % formula then
    derives the payroll rate at runtime.
    """

    _inherit = "res.company"

    l10n_pa_css_risk_grade = fields.Integer(
        string="Panama CSS Professional Risk Grade",
        help=(
            "Grado de riesgo profesional asignado por la CSS al empleador. "
            "Decreto de Gabinete 68/1970 art. 48-51. "
            "La tasa de la prima patronal de Riesgos Profesionales es "
            "grado × 0.07 % (siete centésimos por ciento). Por ejemplo, "
            "grado 8 = 0.56 %, grado 30 = 2.10 %. "
            "Si el grado es cero, se usa el parámetro global "
            "l10n_pa_professional_risk_employer_rate."
        ),
        default=0,
    )

    @api.model
    def l10n_pa_professional_risk_rate(self, company=None):
        """Resolve the active professional-risk rate for this company.

        Returns ``grade × 0.0007`` if a positive grade is configured;
        otherwise 0.0. The salary rule combines this with the global
        ``l10n_pa_professional_risk_employer_rate`` parameter so callers
        can fall back when the company grade is unset.
        """
        company = company or self
        if not company:
            return 0.0
        grade = company.l10n_pa_css_risk_grade or 0
        if grade <= 0:
            return 0.0
        return calculations.professional_risk_rate_from_grade(grade)
