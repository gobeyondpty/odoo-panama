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
        help="Proveedor de Autorización Calificado (PAC) que la "
             "compañía utiliza para emitir facturas electrónicas a DGI.",
    )
    l10n_pa_pac_environment = fields.Selection(
        [
            ('test', "Pruebas / Sandbox"),
            ('prod', "Producción"),
        ],
        default='test',
        string="Ambiente PAC",
        help="Ambiente del PAC. En 'Pruebas' las facturas no son fiscales.",
    )
    l10n_pa_sfep_branch = fields.Char(
        string="Sucursal SFEP",
        size=4,
        default='0001',
        help="Código de sucursal del SFEP (4 dígitos, dSucEm).",
    )
    l10n_pa_sfep_emission_point = fields.Char(
        string="Punto de Emisión",
        size=3,
        default='001',
        help="Punto de facturación SFEP (3 dígitos, dPtoFacDF).",
    )
    l10n_pa_sfep_emission_type = fields.Selection(
        [
            ('01', "Operación normal"),
            ('02', "Contingencia"),
            ('03', "Provisional"),
            ('04', "Reemplazo"),
        ],
        default='01',
        string="Tipo de Emisión",
        help="Modalidad de emisión por defecto (iTpEmis).",
    )
    l10n_pa_sfep_form_cafe = fields.Selection(
        [
            ('1', "PDF estándar DGI"),
            ('2', "Diseño propio del emisor"),
            ('3', "Sin generación de CAFE"),
        ],
        default='1',
        string="Formato CAFE",
        help="Forma de generación del CAFE (iFormCafe).",
    )
    l10n_pa_sfep_delivery_cafe = fields.Selection(
        [
            ('1', "Impreso al receptor"),
            ('2', "Electrónico al receptor"),
            ('3', "No se entrega CAFE"),
        ],
        default='2',
        string="Entrega CAFE",
        help="Manera de entrega del CAFE al receptor (iEntCafe).",
    )
    l10n_pa_certificate_id = fields.Binary(
        string="Certificado de Firma Electrónica (.p12)",
        attachment=True,
        help="Certificado PKCS#12 emitido por Registro Público / Firma "
             "Electrónica usado para firmar documentos DGI.",
    )
    l10n_pa_certificate_password = fields.Char(
        string="Contraseña del Certificado",
        help="Almacenada como ir.config_parameter cifrado por Odoo. "
             "No imprimir en logs ni respuestas API.",
    )
    l10n_pa_certificate_filename = fields.Char(string="Nombre del Archivo del Certificado")

    @api.model
    def _l10n_pa_pac_provider_selection(self):
        """Returns the list of registered PAC providers.

        Concrete provider modules override this method via inheritance
        and append their own entry to the returned list. The base
        implementation contains only the 'none' placeholder so the
        field is usable when no provider is installed.
        """
        return [('none', "Sin PAC configurado")]
