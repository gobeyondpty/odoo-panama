# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


# Withholding agent classification per Decreto Ejecutivo 84 de 26 de
# agosto de 2005, artículo 19. The DGI publishes the annual list of
# designated agents under literal d) before September 1 each year for
# the following fiscal period.
WH_AGENT_TYPES = [
    ('a', 'a) Estado / entidad estatal no exenta'),
    ('b', 'b) Pagador a no domiciliados'),
    ('c', 'c) Sociedad sin personería jurídica / Joint Venture'),
    ('d', 'd) Gran comprador (compras anuales >= B/.5,000,000)'),
    ('e', 'e) Administrador de tarjetas de débito y crédito'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pa_wh_agent_type = fields.Selection(
        selection=WH_AGENT_TYPES,
        string='Tipo de Agente de Retención ITBMS',
        help=(
            "Tipo de agente de retención del ITBMS bajo el cual está "
            "designada la empresa. Determina la matriz de retenciones "
            "aplicables a sus pagos a proveedores. Una empresa puede "
            "tener más de un tipo en la práctica; configurar el principal "
            "y aplicar manualmente las retenciones específicas que "
            "correspondan."
        ),
    )
