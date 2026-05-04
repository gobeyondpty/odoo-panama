# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


# Entity classification used on Form 43 (Informe de Compras e
# Importaciones). Per the Form 43 ayuda technical reference.
PA_ENTITY_TYPES = [
    ('J', 'Jurídico'),
    ('N', 'Natural'),
    ('E', 'Extranjero'),
]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_pa_entity_type = fields.Selection(
        selection=PA_ENTITY_TYPES,
        string='Tipo de Persona (Panamá)',
        help=(
            "Clasificación de la persona para reportes DGI (Formulario 43, "
            "Anexo 95, Formulario 4331)."
        ),
    )

    l10n_pa_certificado_no_contribuyente = fields.Boolean(
        string='Certificado de No Contribuyente del ITBMS',
        help=(
            "El proveedor posee Certificado de No Contribuyente del ITBMS "
            "vigente (ingresos brutos anuales menores a B/.36,000). "
            "Cuando está marcado, no se aplica retención de ITBMS sobre "
            "los pagos a este proveedor (Decreto Ejecutivo 84 de 2005)."
        ),
    )

    l10n_pa_certificado_actividad_exenta = fields.Boolean(
        string='Certificado de Actividades Exentas del ITBMS',
        help=(
            "El proveedor posee Certificado de Actividades Exentas del "
            "ITBMS vigente (Resolución 201-19513 de 2015). Cuando está "
            "marcado, no se aplica retención de ITBMS — el certificado "
            "debe ser presentado al agente de retención y verificado en "
            "el portal eTax2 de la DGI antes de cada uso."
        ),
    )

    l10n_pa_es_intermediario = fields.Boolean(
        string='Actúa como Intermediario',
        help=(
            "Cuando el proveedor actúa como intermediario, sólo se "
            "retiene el 50% del ITBMS sobre la comisión, no sobre el "
            "monto total facturado."
        ),
    )
