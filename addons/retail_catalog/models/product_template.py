from odoo import api, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _prepare_retail_product_vals(self, vals):
        vals = dict(vals)
        product_type = vals.get("type") or "consu"
        vals["type"] = product_type
        if product_type == "consu":
            vals.setdefault("is_storable", True)
        vals.setdefault("purchase_ok", True)
        vals.setdefault("sale_ok", True)
        vals.setdefault("available_in_pos", True)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._prepare_retail_product_vals(vals) for vals in vals_list]
        return super().create(vals_list)
