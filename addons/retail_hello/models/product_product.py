from odoo import models


class ProductProduct(models.Model):
    _inherit = "product.product"

    _default_code_unique = models.UniqueIndex(
        "(default_code) WHERE default_code IS NOT NULL AND default_code != ''"
    )