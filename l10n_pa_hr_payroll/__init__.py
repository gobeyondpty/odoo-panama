from . import models


def post_init_hook(env):
    """Deactivate duplicate BASIC/GROSS/NET rules left behind by Odoo's
    default scaffolding. Run per Panama structure (PA_REGULAR, PA_DECIMO,
    PA_LIQUIDACION).
    """
    structure_xmlids = (
        "l10n_pa_hr_payroll.l10n_pa_payroll_structure_regular",
        "l10n_pa_hr_payroll.l10n_pa_payroll_structure_decimo",
        "l10n_pa_hr_payroll.l10n_pa_payroll_structure_liquidacion",
    )
    keep_xmlid_codes = {
        "l10n_pa_hr_payroll.l10n_pa_payroll_structure_regular": (
            ("l10n_pa_hr_payroll.l10n_pa_rule_basic", "BASIC"),
            ("l10n_pa_hr_payroll.l10n_pa_rule_gross", "GROSS"),
            ("l10n_pa_hr_payroll.l10n_pa_rule_net", "NET"),
        ),
        "l10n_pa_hr_payroll.l10n_pa_payroll_structure_decimo": (
            ("l10n_pa_hr_payroll.l10n_pa_rule_decimo_basic", "BASIC"),
            ("l10n_pa_hr_payroll.l10n_pa_rule_decimo_gross", "GROSS"),
            ("l10n_pa_hr_payroll.l10n_pa_rule_decimo_net", "NET"),
        ),
        "l10n_pa_hr_payroll.l10n_pa_payroll_structure_liquidacion": (
            ("l10n_pa_hr_payroll.l10n_pa_rule_liq_basic", "BASIC"),
            ("l10n_pa_hr_payroll.l10n_pa_rule_liq_net", "NET"),
        ),
    }

    for struct_xmlid in structure_xmlids:
        struct = env.ref(struct_xmlid, raise_if_not_found=False)
        if not struct:
            continue
        keep_ids = []
        codes = set()
        for rule_xmlid, code in keep_xmlid_codes.get(struct_xmlid, ()):
            rule = env.ref(rule_xmlid, raise_if_not_found=False)
            if rule:
                keep_ids.append(rule.id)
                codes.add(code)
        if not codes:
            continue
        duplicates = env["hr.salary.rule"].search(
            [
                ("struct_id", "=", struct.id),
                ("code", "in", list(codes)),
                ("id", "not in", keep_ids),
                ("active", "=", True),
            ]
        )
        duplicates.write({"active": False})
