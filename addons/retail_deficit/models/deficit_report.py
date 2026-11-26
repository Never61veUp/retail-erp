from datetime import timedelta

from odoo import fields, models, _
from odoo.exceptions import UserError


class RetailDeficitReportWizard(models.TransientModel):
    _name = "retail.deficit.report.wizard"
    _description = "Отчёт по дефицитным товарам"

    date_from = fields.Date(
        string="Дата с",
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
    )
    date_to = fields.Date(
        string="Дата по",
        required=True,
        default=fields.Date.context_today,
    )
    warehouse_ids = fields.Many2many(
        "stock.warehouse",
        string="Магазины/склады",
        domain="[('company_id', 'in', allowed_company_ids)]",
        help="Оставьте пустым, чтобы включить все доступные магазины и склады.",
    )

    def action_generate(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_("Дата начала не может быть позже даты окончания."))

        company_ids = self.env.companies.ids
        domain = [
            ("active", "=", True),
            ("warehouse_id.company_id", "in", company_ids),
        ]
        if self.warehouse_ids:
            domain.append(("warehouse_id", "in", self.warehouse_ids.ids))

        orderpoints = self.env["stock.warehouse.orderpoint"].sudo().search(domain)
        rows = []
        for orderpoint in orderpoints:
            qty_available = orderpoint.qty_on_hand
            min_qty = orderpoint.product_min_qty
            if qty_available > 0 and qty_available >= min_qty:
                continue
            rows.append({
                "product_id": orderpoint.product_id.id,
                "location_id": orderpoint.location_id.id,
                "warehouse_id": orderpoint.warehouse_id.id,
                "qty_available": qty_available,
                "qty_forecast": orderpoint.qty_forecast,
                "product_min_qty": min_qty,
                "uom_id": orderpoint.product_id.uom_id.id,
                "company_id": orderpoint.warehouse_id.company_id.id,
            })

        sales = self._get_sales(
            {row["product_id"] for row in rows},
            company_ids,
        )

        line_model = self.env["retail.deficit.report.line"]
        line_model.search([("wizard_id", "=", self.id)]).unlink()
        line_model.create([dict(
            row,
            wizard_id=self.id,
            sales_qty=sales.get((row["product_id"], row["warehouse_id"]), 0.0),
        ) for row in rows])

        return {
            "type": "ir.actions.act_window",
            "name": _("Дефицит по магазинам"),
            "res_model": "retail.deficit.report.line",
            "view_mode": "list",
            "search_view_id": self.env.ref("retail_deficit.view_retail_deficit_report_line_search").id,
            "domain": [("wizard_id", "=", self.id)],
            "target": "current",
        }

    def _get_sales(self, product_ids, company_ids):
        if not product_ids:
            return {}
        date_from = fields.Datetime.to_datetime(self.date_from)
        date_to = fields.Datetime.to_datetime(self.date_to) + timedelta(days=1)
        product_ids = list(product_ids)
        sales = {}

        pos_lines = self.env["pos.order.line"].sudo().search_read([
            ("order_id.state", "in", ["paid", "done"]),
            ("order_id.date_order", ">=", date_from),
            ("order_id.date_order", "<", date_to),
            ("order_id.company_id", "in", company_ids),
            ("product_id", "in", product_ids),
        ], ["product_id", "qty", "order_id"])
        if pos_lines:
            order_ids = {line["order_id"][0] for line in pos_lines}
            orders = self.env["pos.order"].sudo().browse(list(order_ids)).read(["config_id"])
            config_ids = {order["config_id"][0] for order in orders if order["config_id"]}
            configs = self.env["pos.config"].sudo().browse(list(config_ids)).read(["warehouse_id"])
            config_warehouse = {
                config["id"]: config["warehouse_id"][0] if config["warehouse_id"] else False
                for config in configs
            }
            order_warehouse = {
                order["id"]: config_warehouse.get(order["config_id"][0]) if order["config_id"] else False
                for order in orders
            }
            for line in pos_lines:
                warehouse_id = order_warehouse.get(line["order_id"][0])
                if not warehouse_id:
                    continue
                key = (line["product_id"][0], warehouse_id)
                sales[key] = sales.get(key, 0.0) + line["qty"]

        sale_lines = self.env["sale.order.line"].sudo().search_read([
            ("order_id.state", "in", ["sale"]),
            ("order_id.date_order", ">=", date_from),
            ("order_id.date_order", "<", date_to),
            ("order_id.company_id", "in", company_ids),
            ("product_id", "in", product_ids),
        ], ["product_id", "product_uom_qty", "order_id"])
        if sale_lines:
            order_ids = {line["order_id"][0] for line in sale_lines}
            orders = self.env["sale.order"].sudo().browse(list(order_ids)).read(["warehouse_id"])
            order_warehouse = {
                order["id"]: order["warehouse_id"][0] if order["warehouse_id"] else False
                for order in orders
            }
            for line in sale_lines:
                warehouse_id = order_warehouse.get(line["order_id"][0])
                if not warehouse_id or not line["product_id"]:
                    continue
                key = (line["product_id"][0], warehouse_id)
                sales[key] = sales.get(key, 0.0) + line["product_uom_qty"]

        return sales


class RetailDeficitReportLine(models.TransientModel):
    _name = "retail.deficit.report.line"
    _description = "Строка отчёта по дефициту"
    _order = "sales_qty desc, product_id"

    wizard_id = fields.Many2one(
        "retail.deficit.report.wizard",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one("product.product", string="Товар", readonly=True)
    location_id = fields.Many2one("stock.location", string="Точка", readonly=True)
    warehouse_id = fields.Many2one("stock.warehouse", string="Склад", readonly=True)
    qty_available = fields.Float(string="Доступный остаток", readonly=True)
    qty_forecast = fields.Float(string="Прогноз", readonly=True)
    product_min_qty = fields.Float(string="Порог (min)", readonly=True)
    sales_qty = fields.Float(string="Продажи за период", readonly=True)
    uom_id = fields.Many2one("uom.uom", string="Ед. изм.", readonly=True)
    company_id = fields.Many2one("res.company", string="Компания", readonly=True)
