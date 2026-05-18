# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models


def post_init_hook(env):
    env["hr.employee"]._l10n_pa_ensure_vacation_allocations()
