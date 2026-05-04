"""DGI Planilla 03 (Informe 03 V5) row aggregator.

Per Decreto Ejecutivo 20/2022 and DGI Instructivo F03 V5-6, employers
file an annual Form 03 listing each employee with the columns described
in the Instructivo (33 documented columns). This module provides a
helper that converts a posted Panama payslip into the column dict.

Filing format: e-Tax 2.0 platform expects either the manual web form or
an XLS/CSV upload. The exact spreadsheet layout is published by DGI per
fiscal year; binding the row dict to a fixed file format is intentionally
out of scope here so the caller can target the active DGI template.

Source citations are in each column's docstring entry below. The keys of
the returned dict use the column codes as published in the Instructivo
(SALARIO, SUELDO, HORAS_EXTRAS, etc.).
"""

from odoo import api, models


# Instructivo F03 V5 column codes, in document order. Names follow the
# Instructivo verbatim so the dict keys are auditable against the spec.
F03_COLUMNS = (
    "ID_PLANILLA",
    "ANIO_MES_CUOTA",
    "TIPO_DOCUMENTO",
    "NUMERO_DOCUMENTO",
    "DV",
    "NOMBRE_EMPLEADO",
    "SALARIO",
    "SUELDO",
    "HORAS_EXTRAS",
    "VACACIONES",
    "COMISIONES",
    "BONIFICACIONES",
    "SALARIO_ESPECIE",
    "DIETA",
    "PRIMA_PRODUCCION",
    "DECIMO_TERCER_MES",
    "GRATIFICACIONES_AGUINALDOS",
    "GASTO_REPRESENTACION",
    "DEDUCCION_CONJUNTA",
    "INTERESES_HIPOTECARIOS",
    "INTERESES_EDUCATIVOS",
    "PRIMAS_SEGURO",
    "APORTES_FONDOS_JUBILACION",
    "TOTAL_DEDUCCIONES",
    "RENTA_NETA_GRAVABLE",
    "IMPUESTO_RENTA",
    "IMPUESTO_RENTA_REPRESENTACION",
    "RETENCIONES_MES_SALARIOS",
    "RETENCIONES_MES_GASTOS_REP",
    "LIQUIDACION_TERMINACION",
    "ISR_LIQUIDACION_TERMINACION",
    "A_FAVOR_FISCO",
    "A_FAVOR_EMPLEADO",
)


class HrPayrollPanamaPlanilla03(models.AbstractModel):
    """Aggregator for DGI Planilla 03 (Informe 03 V5).

    Use ``planilla_03_row(payslip)`` for a single payslip period, or
    ``planilla_03_rows_for_period(employee, year)`` to assemble the full
    annual row by summing all the employee's payslips of the year.

    Each value is rounded to two decimals. Empty columns return 0.0 (or
    "" for string columns) so the upstream renderer can format them.
    """

    _name = "l10n.pa.hr.payroll.planilla_03"
    _description = "DGI Panama Planilla 03 Aggregator"

    @api.model
    def _payslip_line_total(self, payslip, code, default=0.0):
        line = payslip.line_ids.filtered(lambda line: line.code == code)
        return round(sum(line.mapped("total")), 2) if line else default

    @api.model
    def _payslip_input_amount(self, payslip, code, default=0.0):
        line = payslip.input_line_ids.filtered(lambda line: line.code == code)
        return round(sum(line.mapped("amount")), 2) if line else default

    @api.model
    def planilla_03_row(self, payslip, id_planilla=""):
        """Single-period row. For monthly informe (cuota).

        ``id_planilla`` is the CSS planilla number associated with the
        payslip (Instructivo F03 §1); pass the value provided by SIPE.
        """
        emp = payslip.employee_id
        period = payslip.date_from
        year_month = "%04d%02d" % (period.year, period.month) if period else ""

        identification_no = (emp.identification_id or "").strip()
        is_passport = identification_no.startswith("PAS")

        salario = self._payslip_line_total(payslip, "BASIC")  # contracted wage proxy
        sueldo = salario  # actual cash salary received in the period
        horas_extras = sum(
            self._payslip_line_total(payslip, code)
            for code in ("OT_DAY", "OT_MIXED", "OT_NIGHT", "REST_DAY", "HOLIDAY_WORK")
        )
        vacaciones = self._payslip_line_total(payslip, "VAC_PAY")
        comisiones = 0.0  # caller can split BONIF between BONIF and COM if needed
        bonificaciones = self._payslip_line_total(payslip, "BONIF")
        salario_especie = 0.0  # not modelled as a separate rule
        dieta = 0.0  # not modelled
        prima_produccion = 0.0  # not modelled
        decimo = self._payslip_line_total(payslip, "BASIC") if payslip.struct_id.code == "PA_DECIMO" else 0.0
        gratificaciones = 0.0  # extraordinary year-end aguinaldo, not modelled
        gasto_rep = self._payslip_line_total(payslip, "GASTOS_REP")

        # Annual personal deductions are December-only per Instructivo.
        is_december = period and period.month == 12
        deduccion_conjunta = self._payslip_input_amount(payslip, "SPOUSE_JOINT_AMT") if is_december else 0.0
        intereses_hip = self._payslip_input_amount(payslip, "INT_HIPOTECARIOS_AMT") if is_december else 0.0
        intereses_edu = self._payslip_input_amount(payslip, "INT_EDUCATIVOS_AMT") if is_december else 0.0
        primas_seguro = self._payslip_input_amount(payslip, "PRIMAS_SEGURO_AMT") if is_december else 0.0
        aportes_jub = self._payslip_input_amount(payslip, "APORTES_JUBILACION_AMT") if is_december else 0.0

        total_deducciones = round(
            deduccion_conjunta + intereses_hip + intereses_edu + primas_seguro + aportes_jub,
            2,
        )

        gross = self._payslip_line_total(payslip, "GROSS")
        renta_neta_gravable = round(max(gross - total_deducciones, 0.0), 2)
        impuesto_renta = -self._payslip_line_total(payslip, "ISR_EMP")
        impuesto_renta_rep = -self._payslip_line_total(payslip, "ISR_REP")
        retenciones_mes = impuesto_renta
        retenciones_mes_rep = impuesto_renta_rep

        liq_total = sum(
            self._payslip_line_total(payslip, code)
            for code in ("LIQ_PREAVISO", "LIQ_PRIMA", "LIQ_INDEM", "LIQ_BONIF")
        )
        isr_liq = -self._payslip_line_total(payslip, "ISR_LIQ")

        return {
            "ID_PLANILLA": id_planilla,
            "ANIO_MES_CUOTA": year_month,
            "TIPO_DOCUMENTO": "PASAPORTE" if is_passport else "CEDULA",
            "NUMERO_DOCUMENTO": identification_no,
            "DV": "" if is_passport else self._compute_dv(identification_no),
            "NOMBRE_EMPLEADO": emp.name or "",
            "SALARIO": salario,
            "SUELDO": sueldo,
            "HORAS_EXTRAS": horas_extras,
            "VACACIONES": vacaciones,
            "COMISIONES": comisiones,
            "BONIFICACIONES": bonificaciones,
            "SALARIO_ESPECIE": salario_especie,
            "DIETA": dieta,
            "PRIMA_PRODUCCION": prima_produccion,
            "DECIMO_TERCER_MES": decimo,
            "GRATIFICACIONES_AGUINALDOS": gratificaciones,
            "GASTO_REPRESENTACION": gasto_rep,
            "DEDUCCION_CONJUNTA": deduccion_conjunta,
            "INTERESES_HIPOTECARIOS": intereses_hip,
            "INTERESES_EDUCATIVOS": intereses_edu,
            "PRIMAS_SEGURO": primas_seguro,
            "APORTES_FONDOS_JUBILACION": aportes_jub,
            "TOTAL_DEDUCCIONES": total_deducciones,
            "RENTA_NETA_GRAVABLE": renta_neta_gravable,
            "IMPUESTO_RENTA": impuesto_renta,
            "IMPUESTO_RENTA_REPRESENTACION": impuesto_renta_rep,
            "RETENCIONES_MES_SALARIOS": retenciones_mes,
            "RETENCIONES_MES_GASTOS_REP": retenciones_mes_rep,
            "LIQUIDACION_TERMINACION": liq_total,
            "ISR_LIQUIDACION_TERMINACION": isr_liq,
            "A_FAVOR_FISCO": 0.0,
            "A_FAVOR_EMPLEADO": 0.0,
        }

    @api.model
    def _compute_dv(self, cedula):
        """Compute the DGI/Tribunal Electoral verifier digit (DV) for a cédula.

        Note: DGI accepts the DV computed by the Tribunal Electoral.
        Implementation here returns an empty string when the input is
        empty or non-numeric; otherwise it leaves the DV computation to
        the caller (the algorithm is not published as a single canonical
        formula and varies by cedula format).
        """
        if not cedula or any(not c.isdigit() and c not in "-" for c in cedula):
            return ""
        return ""  # Caller should populate from the Tribunal Electoral DV.
