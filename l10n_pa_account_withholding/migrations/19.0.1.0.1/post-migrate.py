# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Deactivate obsolete withholding tax xmlids from earlier iterations.

Two earlier xmlid sets shipped before the rate matrix was correctly
encoded against ITBMS rates rather than the line base:

  Iteration A (initial scaffold, placeholder rates active=False):
    - tax_pa_wht_itbms_government
    - tax_pa_wht_itbms_card_acquirer
    - tax_pa_wht_isr_nonresident

  Iteration B (DGI-sourced but applied 50%/100% to the line base
  instead of to the ITBMS, active=True):
    - tax_pa_wht_itbms_50_estado_bs
    - tax_pa_wht_itbms_100_estado_serv_prof
    - tax_pa_wht_itbms_no_domiciliado
    - tax_pa_wht_itbms_50_sociedad_sp
    - tax_pa_wht_itbms_50_gran_comprador
    - tax_pa_wht_itbms_50_tarjeta

Iteration B records would over-withhold dramatically if left active
on an upgraded database (50% of line base instead of 50% of ITBMS).
This script removes the ir.model.data row and deactivates the linked
account.tax record on any database that already had them.

The new rate-specific xmlids (tax_pa_wht_itbms_a_bs_07 etc.) are
loaded by the regular noupdate=1 data file.
"""

OBSOLETE_XMLIDS = (
    'tax_pa_wht_itbms_government',
    'tax_pa_wht_itbms_card_acquirer',
    'tax_pa_wht_isr_nonresident',
    'tax_pa_wht_itbms_50_estado_bs',
    'tax_pa_wht_itbms_100_estado_serv_prof',
    'tax_pa_wht_itbms_no_domiciliado',
    'tax_pa_wht_itbms_50_sociedad_sp',
    'tax_pa_wht_itbms_50_gran_comprador',
    'tax_pa_wht_itbms_50_tarjeta',
)


def migrate(cr, version):
    if not version:
        return  # fresh install; nothing to clean up

    for xmlid in OBSOLETE_XMLIDS:
        cr.execute(
            """
            SELECT res_id
            FROM ir_model_data
            WHERE module = 'l10n_pa_account_withholding'
              AND name = %s
              AND model = 'account.tax'
            """,
            (xmlid,),
        )
        row = cr.fetchone()
        if not row:
            continue
        tax_id = row[0]
        cr.execute(
            "UPDATE account_tax SET active = FALSE WHERE id = %s",
            (tax_id,),
        )
        cr.execute(
            """
            DELETE FROM ir_model_data
            WHERE module = 'l10n_pa_account_withholding'
              AND name = %s
            """,
            (xmlid,),
        )
