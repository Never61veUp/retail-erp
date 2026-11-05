from odoo import models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    _x_sku_unique = models.UniqueIndex(
        '("x_SKU") WHERE "x_SKU" IS NOT NULL AND "x_SKU" != \'\''
    )