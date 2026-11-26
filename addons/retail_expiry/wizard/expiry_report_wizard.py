from datetime import timedelta

from odoo import _, fields, models
from odoo.exceptions import UserError


class ExpiryReportWizard(models.TransientModel):
    _name = "retail.expiry.report.wizard"
    _description = "Отбор партий по сроку годности"

    days_ahead = fields.Integer(
        string="Показать партии, истекающие в течение дней",
        default=30,
        required=True,
    )

    def action_view_expiring_lots(self):
        self.ensure_one()
        if self.days_ahead < 0:
            raise UserError(_("Количество дней не может быть отрицательным."))
        now = fields.Datetime.now()
        deadline = now + timedelta(days=self.days_ahead)
        return {
            "type": "ir.actions.act_window",
            "name": _("Партии, истекающие в течение %(days)s дн.", days=self.days_ahead),
            "res_model": "stock.lot",
            "view_mode": "list,form",
            "domain": [
                ("use_expiration_date", "=", True),
                ("product_qty", ">", 0),
                ("expiration_date", ">", fields.Datetime.to_string(now)),
                ("expiration_date", "<=", fields.Datetime.to_string(deadline)),
            ],
            "target": "current",
        }
