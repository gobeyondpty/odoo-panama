# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


# Withholding subject categories per the DGI ITBMS retention matrix
# (Decreto Ejecutivo 84/2005 art. 19, as amended). The first character
# indicates the agent literal that triggers the retention; the rest
# describes the operation.
WH_SUBJECT_SELECTION = [
    ('a_bs', 'a) Estado - bienes y servicios (50%)'),
    ('a_sp', 'a) Estado - servicios profesionales (100%)'),
    ('b_nd', 'b) Pago a no domiciliado (100% via 6.5421%)'),
    ('c_bs', 'c) Sociedad sin personería - bienes y servicios (50%)'),
    ('d_bs', 'd) Gran comprador - bienes, servicios y serv. profesionales (50%)'),
    ('e_tc', 'e) Tarjeta DB/CR - 50% del ITBMS de la venta'),
]


# Form 43 supplier invoice concept categories (Informe de Compras e
# Importaciones). Per the official F43 ayuda reference.
PA_F43_CONCEPT = [
    ('1', '1. Compras y adquisiciones de bienes muebles (gastos de oficina)'),
    ('2', '2. Servicios básicos (electricidad, agua, teléfono)'),
    ('3', '3. Servicios (honorarios, comisiones, mantenimiento, transporte, '
          'seguros, reaseguros, factoring, otros servicios)'),
    ('4', '4. Alquileres por arrendamientos comerciales'),
    ('5', '5. Cargos bancarios, intereses y otros gastos financieros'),
    ('6', '6. Compras o servicios del exterior'),
    ('7', '7. Compras o servicios consolidados'),
]


# Form 43 source classification.
PA_F43_PURCHASE_SOURCE = [
    ('1', '1. Locales'),
    ('2', '2. Importaciones'),
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pa_wh_subject = fields.Selection(
        selection=WH_SUBJECT_SELECTION,
        string='Sujeto de Retención ITBMS',
        help=(
            "Categoría de retención del ITBMS aplicable a este documento "
            "según la matriz DGI. Determina el porcentaje y la base."
        ),
    )

    l10n_pa_f43_concept = fields.Selection(
        selection=PA_F43_CONCEPT,
        string='Concepto Formulario 43',
        help=(
            "Concepto de la compra para el Informe de Compras e "
            "Importaciones (Formulario 43)."
        ),
    )

    l10n_pa_f43_purchase_source = fields.Selection(
        selection=PA_F43_PURCHASE_SOURCE,
        string='Origen Formulario 43',
        default='1',
        help=(
            "Origen de la compra para el Formulario 43: local o importación."
        ),
    )
