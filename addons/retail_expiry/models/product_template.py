from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    storage_conditions = fields.Text(
        string="Условия хранения",
        help="Справочная информация, например: хранить при температуре от +2 до +8 °C.",
    )
