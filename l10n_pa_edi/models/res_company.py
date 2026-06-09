# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Company-level PAC selection and SFEP configuration.

Concrete PAC providers extend the `l10n_pa_pac_provider` Selection by
overriding `_l10n_pa_pac_provider_selection()` to add their own option
(e.g. `('factura_facil', 'Factura Fácil S.A.')`).
"""
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pa_pac_provider = fields.Selection(
        selection='_l10n_pa_pac_provider_selection',
        string="PAC (DGI)",
        help="Qualified Authorization Provider (PAC) used by the company "
             "to issue electronic invoices to DGI.",
    )
    l10n_pa_pac_environment = fields.Selection(
        [
            ('test', "Testing / Sandbox"),
            ('prod', "Production"),
        ],
        default='test',
        string="PAC Environment",
        help="PAC environment. In testing mode, invoices are not fiscal.",
    )
    l10n_pa_sfep_branch = fields.Char(
        string="SFEP Branch",
        size=4,
        default='0001',
        help="SFEP branch code (4 digits, dSucEm).",
    )
    l10n_pa_sfep_emission_point = fields.Char(
        string="Emission Point",
        size=3,
        default='001',
        help="SFEP billing point (3 digits, dPtoFacDF).",
    )
    l10n_pa_sfep_emission_type = fields.Selection(
        [
            ('01', "Normal operation"),
            ('02', "Contingency"),
            ('03', "Provisional"),
            ('04', "Replacement"),
        ],
        default='01',
        string="Emission Type",
        help="Default emission mode (iTpEmis).",
    )
    l10n_pa_sfep_form_cafe = fields.Selection(
        [
            ('1', "No CAFE generation"),
            ('2', "Paper roll"),
            ('3', "Letter-size paper"),
        ],
        default='3',
        string="CAFE Format",
        help="CAFE generation format (iFormCafe), according to DGI PAC Technical Specification v1.00.",
    )
    l10n_pa_sfep_delivery_cafe = fields.Selection(
        [
            ('1', "No CAFE generation"),
            ('2', "Paper CAFE"),
            ('3', "Electronic CAFE"),
        ],
        default='3',
        string="CAFE Delivery",
        help="How the CAFE is delivered to the recipient (iEntCafe), according to DGI PAC Technical Specification v1.00.",
    )
    l10n_pa_certificate_id = fields.Binary(
        string="Electronic Signature Certificate (.p12)",
        attachment=True,
        help="PKCS#12 certificate issued by Registro Publico / Firma "
             "Electronica used to sign DGI documents.",
    )
    l10n_pa_certificate_password = fields.Char(
        string="Certificate Password",
        help="Stored as an Odoo-encrypted ir.config_parameter. Do not print "
             "it in logs or API responses.",
    )
    l10n_pa_certificate_filename = fields.Char(string="Certificate Filename")

    @api.model
    def _l10n_pa_pac_provider_selection(self):
        """Returns the list of registered PAC providers.

        Concrete provider modules override this method via inheritance
        and append their own entry to the returned list. The base
        implementation contains only the 'none' placeholder so the
        field is usable when no provider is installed.
        """
        return [('none', "No PAC configured")]
