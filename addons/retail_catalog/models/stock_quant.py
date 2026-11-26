from odoo import fields, models


class StockQuant(models.Model):
    _inherit = "stock.quant"

    retail_supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        compute="_compute_retail_supplier_id",
        search="_search_retail_supplier_id",
    )

    def _compute_retail_supplier_id(self):
        for quant in self:
            quant.retail_supplier_id = quant.product_id.seller_ids[:1].partner_id

    def _search_retail_supplier_id(self, operator, value):
        return [("product_id.seller_ids.partner_id", operator, value)]
