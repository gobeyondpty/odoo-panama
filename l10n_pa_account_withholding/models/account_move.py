# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.fields import Command


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
        compute='_compute_l10n_pa_wh_subject',
        store=True,
        readonly=False,
        help=(
            "Categoría de retención del ITBMS aplicable a este documento "
            "según la matriz DGI. Determina el porcentaje y la base."
        ),
    )
    l10n_pa_suggested_wh_tax_id = fields.Many2one(
        comodel_name='account.tax',
        string='Retención ITBMS sugerida',
        compute='_compute_l10n_pa_suggested_wh_tax_id',
        check_company=True,
        help=(
            "Retención de ITBMS sugerida a partir del tipo de agente de la "
            "compañía, certificados del proveedor y tasa ITBMS del documento."
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

    @api.depends(
        'move_type',
        'company_id.l10n_pa_wh_agent_type',
        'commercial_partner_id.country_id',
    )
    def _compute_l10n_pa_wh_subject(self):
        for move in self:
            if move.move_type not in ('in_invoice', 'in_refund', 'out_invoice', 'out_refund'):
                move.l10n_pa_wh_subject = False
                continue
            agent_type = move.company_id.l10n_pa_wh_agent_type
            partner = move.commercial_partner_id
            is_foreign = bool(partner.country_id and partner.country_id.code != 'PA')
            if agent_type == 'b' or (move.move_type in ('in_invoice', 'in_refund') and is_foreign):
                move.l10n_pa_wh_subject = 'b_nd'
            elif agent_type == 'a':
                move.l10n_pa_wh_subject = 'a_bs'
            elif agent_type == 'c':
                move.l10n_pa_wh_subject = 'c_bs'
            elif agent_type == 'd':
                move.l10n_pa_wh_subject = 'd_bs'
            elif agent_type == 'e' and move.move_type in ('out_invoice', 'out_refund'):
                move.l10n_pa_wh_subject = 'e_tc'
            else:
                move.l10n_pa_wh_subject = False

    @api.depends(
        'l10n_pa_wh_subject',
        'company_id',
        'commercial_partner_id.l10n_pa_certificado_no_contribuyente',
        'commercial_partner_id.l10n_pa_certificado_actividad_exenta',
        'invoice_line_ids.tax_ids',
        'invoice_line_ids.display_type',
    )
    def _compute_l10n_pa_suggested_wh_tax_id(self):
        for move in self:
            move.l10n_pa_suggested_wh_tax_id = move._l10n_pa_get_suggested_wh_tax()

    def _l10n_pa_get_itbms_rate(self):
        self.ensure_one()
        taxes = self.invoice_line_ids.filtered(
            lambda line: line.display_type == 'product'
        ).tax_ids.filtered(
            lambda tax: (
                tax.country_id.code == 'PA'
                and tax.amount_type == 'percent'
                and tax.amount in (7.0, 10.0, 15.0)
                and not tax.is_withholding_tax_on_payment
            )
        )
        return taxes[:1].amount if taxes else 0.0

    def _l10n_pa_get_suggested_wh_tax_xmlid(self):
        self.ensure_one()
        subject = self.l10n_pa_wh_subject
        partner = self.commercial_partner_id
        if (
            not subject
            or partner.l10n_pa_certificado_no_contribuyente
            or partner.l10n_pa_certificado_actividad_exenta
        ):
            return False
        if subject == 'b_nd':
            return 'tax_pa_wht_itbms_b_no_domiciliado'
        rate = int(self._l10n_pa_get_itbms_rate())
        if rate not in (7, 10, 15):
            return False
        suffix = f'{rate:02d}'
        return {
            'a_bs': f'tax_pa_wht_itbms_a_bs_{suffix}',
            'a_sp': f'tax_pa_wht_itbms_a_sp_{suffix}',
            'c_bs': f'tax_pa_wht_itbms_c_bs_{suffix}',
            'd_bs': f'tax_pa_wht_itbms_d_{suffix}',
            'e_tc': f'tax_pa_wht_itbms_e_{suffix}',
        }.get(subject)

    def _l10n_pa_get_suggested_wh_tax(self):
        self.ensure_one()
        xmlid = self._l10n_pa_get_suggested_wh_tax_xmlid()
        if not xmlid:
            return self.env['account.tax']
        return self.env['account.chart.template'].with_company(self.company_id).ref(
            xmlid,
            raise_if_not_found=False,
        )

    def action_l10n_pa_apply_suggested_wh_tax(self):
        for move in self:
            tax = move.l10n_pa_suggested_wh_tax_id
            if not tax:
                continue
            product_lines = move.invoice_line_ids.filtered(
                lambda line: line.display_type == 'product'
            )
            for line in product_lines:
                if tax not in line.tax_ids:
                    line.tax_ids = [Command.link(tax.id)]
        return True
