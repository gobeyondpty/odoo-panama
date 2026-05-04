# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
from collections import defaultdict
from datetime import date

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError

from ..lib.sipe_writer import SipeRow, numeric_field_keys, write_sipe_xlsx


class L10nPaSipeExportWizard(models.TransientModel):
    _name = "l10n.pa.sipe.export.wizard"
    _description = "Exportar planilla SIPE (CSS Panamá)"

    company_id = fields.Many2one(
        "res.company",
        string="Empleador",
        required=True,
        default=lambda self: self.env.company,
    )
    date_start = fields.Date(
        string="Periodo - Fecha desde",
        required=True,
        default=lambda self: date.today().replace(day=1),
    )
    date_end = fields.Date(
        string="Periodo - Fecha hasta",
        required=True,
        default=lambda self: date.today(),
    )
    state = fields.Selection(
        selection=[("draft", "Borrador"), ("done", "Generado")],
        default="draft",
        readonly=True,
    )
    file_data = fields.Binary(string="Archivo XLSX", readonly=True)
    file_name = fields.Char(readonly=True)

    def _get_payslips(self):
        return self.env["hr.payslip"].search([
            ("company_id", "=", self.company_id.id),
            ("state", "in", ("validated", "paid")),
            ("date_from", ">=", self.date_start),
            ("date_to", "<=", self.date_end),
        ])

    def _build_rows(self):
        self.ensure_one()
        if self.date_end < self.date_start:
            raise ValidationError(_("Fecha hasta no puede ser anterior a fecha desde."))

        payslips = self._get_payslips()
        if not payslips:
            raise UserError(_(
                "No hay planillas confirmadas para %(empleador)s en el "
                "periodo %(d1)s a %(d2)s.",
                empleador=self.company_id.name,
                d1=self.date_start,
                d2=self.date_end,
            ))

        # Aggregate per (employee_id, sipe_column) → summed line.total.
        amounts = defaultdict(lambda: defaultdict(float))
        unmapped_rules = set()
        for line in payslips.mapped("line_ids"):
            sipe_col = line.salary_rule_id.l10n_pa_sipe_column
            if not sipe_col:
                if line.appears_on_payslip:
                    unmapped_rules.add(line.salary_rule_id.code)
                continue
            amounts[line.employee_id.id][sipe_col] += line.total

        if not amounts:
            raise UserError(_(
                "Ninguna línea de planilla tiene una columna SIPE asignada. "
                "Configure el campo 'SIPE Column' en las reglas salariales "
                "que deben fluir al archivo SIPE."
            ))

        rows = []
        employees = self.env["hr.employee"].browse(list(amounts.keys()))
        for employee in employees:
            self._validate_employee(employee)
            nombre, apellido = employee._l10n_pa_sipe_split_name()
            row_kwargs = {
                "tipo_documento": employee.l10n_pa_sipe_id_type,
                "numero_documento": (employee.identification_id or "").strip(),
                "numero_seguro_social": (employee.l10n_pa_css_number or "").strip(),
                "nombre": nombre,
                "apellido": apellido,
            }
            for key in numeric_field_keys():
                row_kwargs[key] = round(amounts[employee.id].get(key, 0.0), 2)
            rows.append(SipeRow(**row_kwargs))

        if unmapped_rules:
            self.env["bus.bus"]._sendone(
                self.env.user.partner_id,
                "simple_notification",
                {
                    "type": "warning",
                    "title": _("Reglas salariales sin columna SIPE"),
                    "message": _(
                        "Las siguientes reglas no se incluyeron en el "
                        "archivo SIPE: %s",
                        ", ".join(sorted(unmapped_rules)),
                    ),
                },
            )
        return rows

    def _validate_employee(self, employee):
        missing = []
        if not employee.identification_id:
            missing.append(_("Número de Documento (identification_id)"))
        if not employee.l10n_pa_css_number:
            missing.append(_("Número de Seguro Social (l10n_pa_css_number)"))
        if not employee.l10n_pa_sipe_id_type:
            missing.append(_("Tipo de Documento (l10n_pa_sipe_id_type)"))
        if missing:
            raise ValidationError(_(
                "Empleado %(name)s no puede ser exportado a SIPE. Faltan: "
                "%(missing)s",
                name=employee.display_name,
                missing=", ".join(missing),
            ))

    def action_generate(self):
        self.ensure_one()
        rows = self._build_rows()
        xlsx_bytes = write_sipe_xlsx(rows)
        period_tag = self.date_start.strftime("%Y%m") if self.date_start else "periodo"
        self.write({
            "file_data": base64.b64encode(xlsx_bytes),
            "file_name": f"sipe_planilla_{period_tag}.xlsx",
            "state": "done",
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
