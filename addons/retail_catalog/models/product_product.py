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

    def _find_retail_default_code_duplicate(self, default_code, exclude_ids=None):
        domain = [("default_code", "=", default_code)]
        if exclude_ids:
            domain.append(("id", "not in", list(exclude_ids)))
        return self.with_context(active_test=False).search(domain, limit=1)

    def _raise_retail_default_code_duplicate(self, default_code, duplicate=None):
        if duplicate:
            message = self.env._(
                "Артикул «%s» уже используется товаром «%s».",
                default_code,
                duplicate.display_name,
            )
        else:
            message = self.env._("Артикул «%s» уже используется.", default_code)
        raise ValidationError(message)

    @api.model_create_multi
    def create(self, vals_list):
        seen_codes = set()
        for vals in vals_list:
            for field_name in ("default_code", "barcode"):
                if field_name in vals:
                    vals[field_name] = self._normalize_retail_code(vals[field_name])
            default_code = vals.get("default_code")
            if default_code:
                duplicate = self._find_retail_default_code_duplicate(default_code)
                if duplicate or default_code in seen_codes:
                    self._raise_retail_default_code_duplicate(default_code, duplicate)
                seen_codes.add(default_code)
        return super().create(vals_list)

    def write(self, vals):
        for field_name in ("default_code", "barcode"):
            if field_name in vals:
                vals[field_name] = self._normalize_retail_code(vals[field_name])
        default_code = vals.get("default_code")
        if default_code:
            if len(self) > 1:
                self._raise_retail_default_code_duplicate(default_code)
            duplicate = self._find_retail_default_code_duplicate(
                default_code,
                exclude_ids=self.ids,
            )
            if duplicate:
                self._raise_retail_default_code_duplicate(default_code, duplicate)
        return super().write(vals)

    @api.constrains("default_code")
    def _check_retail_default_code_unique(self):
        for product in self:
            if not product.default_code:
                continue
            duplicate = self._find_retail_default_code_duplicate(
                product.default_code,
                exclude_ids=product.ids,
            )
            if duplicate:
                self._raise_retail_default_code_duplicate(product.default_code, duplicate)
