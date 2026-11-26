import logging
from collections import defaultdict

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.tools.float_utils import float_round


_logger = logging.getLogger(__name__)


class StockLot(models.Model):
    _inherit = "stock.lot"

    retail_expiry_notification_sent = fields.Boolean(
        string="Уведомление о сроке отправлено",
        default=False,
        copy=False,
        readonly=True,
    )

    def write(self, vals):
        if {"expiration_date", "alert_date"} & vals.keys():
            vals = dict(vals, retail_expiry_notification_sent=False)
        return super().write(vals)

    @api.model
    def _alert_date_exceeded(self):
        # Replace the generic product-responsible reminder with detailed warehouse activities.
        now = fields.Datetime.now()
        lots = self.search([
            ("alert_date", "<=", fields.Date.today()),
            ("retail_expiry_notification_sent", "=", False),
        ])
        if not lots:
            return

        quants = self.env["stock.quant"].search([
            ("lot_id", "in", lots.ids),
            ("quantity", ">", 0),
            ("location_id.usage", "=", "internal"),
        ])
        quantities = defaultdict(float)
        for quant in quants:
            quantities[quant.lot_id.id] += quant.quantity

        warehouse_group = self.env.ref("stock.group_stock_user")
        for lot in quants.mapped("lot_id"):
            quantity = quantities[lot.id]
            if not lot.expiration_date or lot.expiration_date <= now:
                lot.write({
                    "retail_expiry_notification_sent": True,
                    "product_expiry_reminded": True,
                })
                continue

            users = warehouse_group.user_ids.filtered(
                lambda user: user.active
                and not user.share
                and (not lot.company_id or lot.company_id in user.company_ids)
            )
            if not users:
                _logger.error(
                    "No active warehouse users are available to notify for lot %s (ID %s).",
                    lot.name,
                    lot.id,
                )
                continue

            quantity = float_round(
                quantity, precision_rounding=lot.product_id.uom_id.rounding
            )
            quantity_text = "%s %s" % (quantity, lot.product_id.uom_id.name)
            note = Markup(
                "<p>{}</p><ul>"
                "<li><b>{}:</b> {}</li>"
                "<li><b>{}:</b> {}</li>"
                "<li><b>{}:</b> {}</li>"
                "<li><b>{}:</b> {}</li>"
                "</ul>"
            ).format(
                _("Приближается срок годности товара."),
                _("Товар"),
                lot.product_id.display_name,
                _("Партия"),
                lot.name,
                _("Количество на складе"),
                quantity_text,
                _("Срок годности"),
                fields.Datetime.to_string(lot.expiration_date),
            )
            for user in users:
                lot.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=user.id,
                    summary=_("Приближается срок годности"),
                    note=note,
                )
            lot.write({
                "retail_expiry_notification_sent": True,
                "product_expiry_reminded": True,
            })
