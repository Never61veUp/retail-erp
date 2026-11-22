from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class RetailPurchaseDiscrepancy(models.Model):
    _name = "retail.purchase.discrepancy"
    _description = "Purchase Delivery Discrepancy"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    purchase_order_id = fields.Many2one(
        "purchase.order",
        string="Purchase Order",
        required=True,
        ondelete="cascade",
        index=True,
    )
    purchase_line_id = fields.Many2one(
        "purchase.order.line",
        string="Purchase Line",
        required=True,
        ondelete="cascade",
        index=True,
    )
    picking_id = fields.Many2one(
        "stock.picking",
        string="Receiving",
        ondelete="set null",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        related="purchase_line_id.product_id",
        store=True,
        readonly=True,
    )
    discrepancy_type = fields.Selection(
        [
            ("under", "Under-delivery"),
            ("over", "Over-delivery"),
            ("damage", "Damaged"),
        ],
        string="Type",
        required=True,
        tracking=True,
        index=True,
    )
    quantity = fields.Float(string="Quantity", required=True, tracking=True)
    reason = fields.Text(string="Reason", required=True, tracking=True)
    date = fields.Datetime(
        string="Date",
        default=fields.Datetime.now,
        required=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Recorded By",
        default=lambda self: self.env.user,
        required=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="purchase_order_id.company_id",
        store=True,
        readonly=True,
    )

    @api.constrains("quantity")
    def _check_quantity(self):
        for discrepancy in self:
            if discrepancy.quantity <= 0:
                raise ValidationError(_("Discrepancy quantity must be greater than zero."))

    @api.constrains("purchase_line_id", "purchase_order_id")
    def _check_purchase_line(self):
        for discrepancy in self:
            if (
                discrepancy.purchase_line_id
                and discrepancy.purchase_line_id.order_id != discrepancy.purchase_order_id
            ):
                raise ValidationError(
                    _("The purchase line must belong to the selected purchase order.")
                )

    @api.constrains("picking_id", "purchase_order_id")
    def _check_picking(self):
        for discrepancy in self:
            if not discrepancy.picking_id:
                continue
            picking_ids = getattr(
                discrepancy.purchase_order_id,
                "picking_ids",
                self.env["stock.picking"],
            )
            if discrepancy.picking_id not in picking_ids:
                raise ValidationError(
                    _("The receiving must belong to the selected purchase order.")
                )

    @api.constrains("reason")
    def _check_reason(self):
        for discrepancy in self:
            if not discrepancy.reason or not discrepancy.reason.strip():
                raise ValidationError(
                    _("Please provide a reason for the discrepancy.")
                )

    @api.onchange("purchase_line_id")
    def _onchange_purchase_line_id(self):
        if self.purchase_line_id:
            self.purchase_order_id = self.purchase_line_id.order_id


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    retail_discrepancy_ids = fields.One2many(
        "retail.purchase.discrepancy",
        "purchase_order_id",
        string="Delivery Discrepancies",
    )
    retail_discrepancy_count = fields.Integer(
        compute="_compute_retail_discrepancy_count",
        string="Discrepancy Count",
    )

    def _compute_retail_discrepancy_count(self):
        for order in self:
            order.retail_discrepancy_count = len(order.retail_discrepancy_ids)

    def action_record_retail_discrepancy(self):
        self.ensure_one()
        return {
            "name": _("Record Delivery Discrepancy"),
            "type": "ir.actions.act_window",
            "res_model": "retail.purchase.discrepancy.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_purchase_order_id": self.id,
            },
        }

    def action_open_retail_discrepancies(self):
        self.ensure_one()
        return {
            "name": _("Delivery Discrepancies"),
            "type": "ir.actions.act_window",
            "res_model": "retail.purchase.discrepancy",
            "view_mode": "list,form",
            "domain": [("purchase_order_id", "=", self.id)],
            "context": {"default_purchase_order_id": self.id},
        }


class RetailPurchaseDiscrepancyWizard(models.TransientModel):
    _name = "retail.purchase.discrepancy.wizard"
    _description = "Record Purchase Delivery Discrepancy"

    purchase_order_id = fields.Many2one(
        "purchase.order",
        string="Purchase Order",
        required=True,
    )
    purchase_line_id = fields.Many2one(
        "purchase.order.line",
        string="Purchase Line",
        required=True,
    )
    picking_id = fields.Many2one("stock.picking", string="Receiving")
    discrepancy_type = fields.Selection(
        [
            ("under", "Under-delivery"),
            ("over", "Over-delivery"),
            ("damage", "Damaged"),
        ],
        string="Type",
        required=True,
    )
    quantity = fields.Float(string="Quantity", required=True)
    reason = fields.Text(string="Reason", required=True)

    @api.onchange("purchase_order_id")
    def _onchange_purchase_order_id(self):
        self.purchase_line_id = False
        self.picking_id = False

    def action_confirm(self):
        self.ensure_one()
        if self.quantity <= 0:
            raise ValidationError(_("Discrepancy quantity must be greater than zero."))
        if not self.reason or not self.reason.strip():
            raise ValidationError(_("Please provide a reason for the discrepancy."))
        if self.purchase_line_id.order_id != self.purchase_order_id:
            raise ValidationError(_("The purchase line must belong to the selected purchase order."))
        if self.picking_id:
            picking_ids = getattr(self.purchase_order_id, "picking_ids", self.env["stock.picking"])
            if self.picking_id not in picking_ids:
                raise ValidationError(_("The receiving must belong to the selected purchase order."))

        discrepancy = self.env["retail.purchase.discrepancy"].create({
            "purchase_order_id": self.purchase_order_id.id,
            "purchase_line_id": self.purchase_line_id.id,
            "picking_id": self.picking_id.id or False,
            "discrepancy_type": self.discrepancy_type,
            "quantity": self.quantity,
            "reason": self.reason.strip(),
        })

        return {
            "name": _("Delivery Discrepancy"),
            "type": "ir.actions.act_window",
            "res_model": "retail.purchase.discrepancy",
            "res_id": discrepancy.id,
            "view_mode": "form",
            "target": "current",
        }
