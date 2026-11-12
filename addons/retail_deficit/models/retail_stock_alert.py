from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RetailStockAlert(models.Model):
    _name = "retail.stock.alert"
    _description = "Stock Deficit Alert"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(default="/", copy=False, readonly=True, index=True)
    orderpoint_id = fields.Many2one(
        "stock.warehouse.orderpoint",
        string="Reordering Rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one(
        related="orderpoint_id.product_id",
        store=True,
        readonly=True,
        index=True,
    )
    location_id = fields.Many2one(
        related="orderpoint_id.location_id",
        store=True,
        readonly=True,
    )
    warehouse_id = fields.Many2one(
        related="orderpoint_id.warehouse_id",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related="orderpoint_id.company_id",
        store=True,
        readonly=True,
    )
    product_min_qty = fields.Float(related="orderpoint_id.product_min_qty", readonly=True)
    product_max_qty = fields.Float(related="orderpoint_id.product_max_qty", readonly=True)
    qty_available = fields.Float(string="On Hand", readonly=True)
    qty_forecast = fields.Float(string="Forecast", readonly=True)
    recommended_qty = fields.Float(string="Recommended Quantity")
    state = fields.Selection(
        [
            ("new", "To Order"),
            ("ordered", "Ordered"),
            ("done", "Resolved"),
        ],
        default="new",
        required=True,
        tracking=True,
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        default=lambda self: self.env.user,
    )
    purchase_order_id = fields.Many2one(
        "purchase.order",
        string="Purchase Order",
        readonly=True,
        copy=False,
    )
    date = fields.Datetime(default=fields.Datetime.now, readonly=True)
    last_check_date = fields.Datetime(readonly=True)

    _orderpoint_uniq = models.Constraint(
        "UNIQUE(orderpoint_id)",
        "Only one stock alert per reordering rule is allowed.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code("retail.stock.alert") or "/"
        return super().create(vals_list)

    def _get_responsible_users(self):
        groups = (
            self.env.ref("purchase.group_purchase_manager")
            | self.env.ref("purchase.group_purchase_user")
        )
        users = groups.mapped("user_ids").filtered(lambda user: user.active and not user.share)
        if not users:
            users = self.env.ref("base.user_admin")
        return users

    def _deficit_body(self):
        self.ensure_one()
        return _(
            "<p><b>Low stock:</b> %(product)s</p>"
            "<ul>"
            "<li>Location: %(location)s</li>"
            "<li>On hand: %(on_hand)s</li>"
            "<li>Forecast: %(forecast)s</li>"
            "<li>Minimum: %(min_qty)s</li>"
            "<li>Recommended to order: %(recommended)s</li>"
            "</ul>",
            product=self.product_id.display_name,
            location=self.location_id.complete_name,
            on_hand=self.qty_available,
            forecast=self.qty_forecast,
            min_qty=self.product_min_qty,
            recommended=self.recommended_qty,
        )

    def _notify_purchasers(self):
        self.ensure_one()
        users = self._get_responsible_users()
        if not users:
            return
        self.message_subscribe(partner_ids=users.partner_id.ids)
        self.message_post(body=self._deficit_body(), partner_ids=users.partner_id.ids)
        activity_type = self.env.ref("mail.mail_activity_data_todo")
        deadline = fields.Date.context_today(self)
        for user in users:
            if self.activity_ids.filtered(lambda activity: activity.user_id == user):
                continue
            self.env["mail.activity"].create({
                "res_model_id": self.env["ir.model"]._get_id(self._name),
                "res_id": self.id,
                "activity_type_id": activity_type.id,
                "user_id": user.id,
                "summary": _("Low stock: %s", self.product_id.display_name),
                "note": self._deficit_body(),
                "date_deadline": deadline,
            })

    def _close_activities(self):
        self.activity_ids.unlink()

    def _refresh_from_orderpoint(self):
        for alert in self:
            orderpoint = alert.orderpoint_id
            vals = {
                "qty_available": orderpoint.qty_on_hand,
                "qty_forecast": orderpoint.qty_forecast,
                "last_check_date": fields.Datetime.now(),
            }
            if alert.state == "new":
                vals["recommended_qty"] = orderpoint.qty_to_order
            alert.write(vals)

    def _get_open_purchase_order(self):
        self.ensure_one()
        if self.purchase_order_id and self.purchase_order_id.state != "cancel":
            return self.purchase_order_id
        return self.env["purchase.order"]

    @api.model
    def _process_orderpoint(self, orderpoint, recompute=True):
        if recompute:
            orderpoint._compute_qty_to_order_computed()
        alert = self.search([("orderpoint_id", "=", orderpoint.id)], limit=1)
        needs_order = orderpoint.qty_to_order > 0
        stock_vals = {
            "qty_available": orderpoint.qty_on_hand,
            "qty_forecast": orderpoint.qty_forecast,
            "last_check_date": fields.Datetime.now(),
        }
        if needs_order:
            open_po = alert._get_open_purchase_order() if alert else self.env["purchase.order"]
            if open_po:
                alert.write(stock_vals)
                return alert
            if not alert:
                responsible = self._get_responsible_users()[:1]
                alert = self.create(dict(
                    stock_vals,
                    orderpoint_id=orderpoint.id,
                    recommended_qty=orderpoint.qty_to_order,
                    state="new",
                    user_id=responsible.id or False,
                ))
                alert._notify_purchasers()
                return alert
            reopen = alert.state in ("done", "ordered")
            vals = dict(stock_vals)
            if reopen:
                vals.update({
                    "state": "new",
                    "recommended_qty": orderpoint.qty_to_order,
                    "purchase_order_id": False,
                    "date": fields.Datetime.now(),
                })
            alert.write(vals)
            if reopen:
                alert._notify_purchasers()
            return alert
        if alert and alert.state != "done":
            alert.write(dict(stock_vals, state="done"))
            alert._close_activities()
        elif alert:
            alert.write(stock_vals)
        return alert

    @api.model
    def _cron_check_stock_alerts(self):
        orderpoints = self.env["stock.warehouse.orderpoint"].search([("active", "=", True)])
        orderpoints._compute_qty_to_order_computed()
        alerts = self.browse()
        for orderpoint in orderpoints:
            if not orderpoint.product_id or not orderpoint.product_id.purchase_ok:
                continue
            alerts |= self._process_orderpoint(orderpoint, recompute=False)
        return alerts

    def action_refresh(self):
        for alert in self:
            alert._refresh_from_orderpoint()
        return True

    def _open_purchase_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "purchase.order",
            "res_id": self.purchase_order_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_create_purchase_order(self):
        self.ensure_one()
        open_po = self._get_open_purchase_order()
        if open_po:
            return self._open_purchase_order()
        if self.recommended_qty <= 0:
            raise UserError(_("Recommended quantity must be greater than zero."))
        seller = self.product_id.seller_ids[:1]
        if not seller:
            raise UserError(_(
                "No vendor is defined for %s. Add a vendor price first.",
                self.product_id.display_name,
            ))
        company = self.company_id or self.env.company
        purchase_order = self.env["purchase.order"].create({
            "partner_id": seller.partner_id.id,
            "origin": self.name,
            "company_id": company.id,
            "currency_id": company.currency_id.id,
            "date_order": fields.Datetime.now(),
            "order_line": [(0, 0, {
                "product_id": self.product_id.id,
                "name": self.product_id.display_name,
                "product_qty": self.recommended_qty,
                "price_unit": seller.price,
                "product_uom_id": self.product_id.uom_id.id,
            })],
        })
        self.write({
            "state": "ordered",
            "purchase_order_id": purchase_order.id,
            "last_check_date": fields.Datetime.now(),
        })
        self.message_post(body=_(
            "Purchase order %s created from this alert.",
            purchase_order.name,
        ))
        self._close_activities()
        return self._open_purchase_order()
