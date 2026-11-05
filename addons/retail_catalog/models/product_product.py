from odoo import api, models
from odoo.exceptions import ValidationError


class ProductProduct(models.Model):
    _inherit = "product.product"

    _retail_default_code_uniq = models.UniqueIndex(
        "(default_code) WHERE default_code IS NOT NULL AND default_code <> ''",
        "Артикул уже используется. Укажите уникальный артикул.",
    )

    def _normalize_retail_code(self, value):
        if isinstance(value, str):
            value = value.strip()
        return value or False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            for field_name in ("default_code", "barcode"):
                if field_name in vals:
                    vals[field_name] = self._normalize_retail_code(vals[field_name])
        return super().create(vals_list)

    def write(self, vals):
        for field_name in ("default_code", "barcode"):
            if field_name in vals:
                vals[field_name] = self._normalize_retail_code(vals[field_name])
        return super().write(vals)

    @api.constrains("default_code")
    def _check_retail_default_code_unique(self):
        for product in self:
            if not product.default_code:
                continue
            duplicate = self.with_context(active_test=False).search([
                ("id", "!=", product.id),
                ("default_code", "=", product.default_code),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    self.env._(
                        "Артикул «%s» уже используется товаром «%s».",
                        product.default_code,
                        duplicate.display_name,
                    )
                )
