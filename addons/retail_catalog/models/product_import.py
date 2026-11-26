import base64
import csv
import io

from odoo import fields, models, _
from odoo.exceptions import UserError

try:
    from openpyxl import load_workbook
except ImportError:  # pragma: no cover - openpyxl is shipped with Odoo
    load_workbook = None


HEADER_MAP = {
    "название": "name",
    "name": "name",
    "артикул": "default_code",
    "default_code": "default_code",
    "internal reference": "default_code",
    "штрихкод": "barcode",
    "barcode": "barcode",
    "категория": "category",
    "category": "category",
    "единица измерения": "uom",
    "uom": "uom",
    "ед. изм.": "uom",
    "закупочная цена": "purchase_price",
    "purchase_price": "purchase_price",
    "розничная цена": "sale_price",
    "sale_price": "sale_price",
}
REQUIRED_COLUMNS = ("name", "default_code")


def _normalize_header(value):
    if value is None:
        return ""
    return str(value).strip().lower().replace("ё", "е")


def _to_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _normalize_code(value):
    text = _to_text(value)
    return text or False


class RetailProductImportWizard(models.TransientModel):
    _name = "retail.product.import.wizard"
    _description = "Импорт товаров из Excel"

    file = fields.Binary(string="Файл", required=True)
    filename = fields.Char(string="Имя файла")

    def action_download_template(self):
        return {
            "type": "ir.actions.act_url",
            "url": "/retail_catalog/static/src/xlsx/product_import_template.xlsx",
            "target": "self",
        }

    def action_import(self):
        self.ensure_one()
        if not self.file:
            raise UserError(_("Загрузите файл."))
        raw = base64.b64decode(self.file)
        rows = self._read_rows(raw)
        if not rows:
            raise UserError(_("Файл пуст."))

        columns = self._map_headers(rows[0])
        missing = [field_name for field_name in REQUIRED_COLUMNS if field_name not in columns]
        if missing:
            raise UserError(_(
                "В файле не найдены обязательные колонки: %s",
                ", ".join(missing),
            ))

        line_model = self.env["retail.product.import.line"]
        line_model.search([("wizard_id", "=", self.id)]).unlink()

        default_category = self.env.ref("product.product_category_all", raise_if_not_found=False)
        if not default_category:
            default_category = self.env["product.category"].sudo().search([], limit=1)
        default_uom = self.env.ref("uom.product_uom_unit", raise_if_not_found=False)
        if not default_uom:
            default_uom = self.env["uom.uom"].sudo().search([], limit=1)

        seen_codes = set()
        seen_barcodes = set()
        errors = 0

        for row_number, row in enumerate(rows[1:], start=2):
            values = {
                field_name: row[index] if index < len(row) else None
                for field_name, index in columns.items()
            }
            if not any(value not in (None, "") for value in values.values()):
                continue

            name = _to_text(values.get("name"))
            default_code = _normalize_code(values.get("default_code"))
            barcode = _normalize_code(values.get("barcode"))
            category_name = _to_text(values.get("category"))
            uom_name = _to_text(values.get("uom"))
            purchase_price = self._to_float(values.get("purchase_price"))
            sale_price = self._to_float(values.get("sale_price"))

            line_vals = {
                "wizard_id": self.id,
                "row_number": row_number,
                "name": name,
                "default_code": default_code or "",
                "barcode": barcode or "",
                "category_name": category_name,
                "uom_name": uom_name,
                "purchase_price": purchase_price or 0.0,
                "sale_price": sale_price or 0.0,
            }

            if not name:
                self._create_line(line_vals, "error", _("Не заполнено название."))
                errors += 1
                continue
            if not default_code:
                self._create_line(line_vals, "error", _("Не заполнен артикул."))
                errors += 1
                continue
            if default_code in seen_codes:
                self._create_line(line_vals, "error", _("Дубликат артикула в файле."))
                errors += 1
                continue
            seen_codes.add(default_code)
            if barcode:
                if barcode in seen_barcodes:
                    self._create_line(line_vals, "error", _("Дубликат штрихкода в файле."))
                    errors += 1
                    continue
                seen_barcodes.add(barcode)

            existing_by_code = self.env["product.product"].sudo().search(
                [("default_code", "=", default_code)], limit=1
            )
            existing_by_barcode = self.env["product.product"].sudo().search(
                [("barcode", "=", barcode)], limit=1
            ) if barcode else self.env["product.product"]
            existing = existing_by_code or existing_by_barcode
            if existing:
                line_vals["product_id"] = existing.id
                self._create_line(line_vals, "skipped", _("Товар уже существует."))
                continue

            category = default_category
            if category_name:
                category = self.env["product.category"].sudo().search(
                    [("name", "=", category_name)], limit=1
                )
                if not category:
                    self._create_line(line_vals, "error", _("Категория «%s» не найдена.", category_name))
                    errors += 1
                    continue
            uom = default_uom
            if uom_name:
                uom = self.env["uom.uom"].sudo().search([("name", "=", uom_name)], limit=1)
                if not uom:
                    self._create_line(line_vals, "error", _("Единица измерения «%s» не найдена.", uom_name))
                    errors += 1
                    continue
            if purchase_price is None:
                self._create_line(line_vals, "error", _("Некорректная закупочная цена."))
                errors += 1
                continue
            if sale_price is None:
                self._create_line(line_vals, "error", _("Некорректная розничная цена."))
                errors += 1
                continue

            try:
                with self.env.cr.savepoint():
                    template = self.env["product.template"].sudo().create({
                        "name": name,
                        "default_code": default_code,
                        "barcode": barcode or False,
                        "categ_id": category.id,
                        "uom_id": uom.id,
                        "standard_price": purchase_price,
                        "list_price": sale_price,
                        "type": "consu",
                        "is_storable": True,
                        "purchase_ok": True,
                        "sale_ok": True,
                        "available_in_pos": True,
                    })
            except Exception as error:
                self._create_line(line_vals, "error", self._error_message(error))
                errors += 1
                continue

            line_vals["product_id"] = template.product_variant_id.id
            self._create_line(line_vals, "imported", _("Импортирован."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Результат импорта товаров"),
            "res_model": "retail.product.import.line",
            "view_mode": "list",
            "search_view_id": self.env.ref("retail_catalog.view_retail_product_import_line_search").id,
            "domain": [("wizard_id", "=", self.id)],
            "context": {"search_default_errors": 1} if errors else {},
            "target": "current",
        }

    def _read_rows(self, raw):
        filename = (self.filename or "").lower()
        if filename.endswith(".csv"):
            return [list(row) for row in csv.reader(io.StringIO(raw.decode("utf-8-sig")))]
        if filename.endswith((".xlsx", ".xlsm")):
            if load_workbook is None:
                raise UserError(_("Для импорта XLSX не установлена библиотека openpyxl."))
            workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            return [list(row) for row in workbook.active.iter_rows(values_only=True)]
        raise UserError(_("Поддерживаются файлы .xlsx и .csv."))

    def _map_headers(self, header):
        columns = {}
        for index, value in enumerate(header):
            field_name = HEADER_MAP.get(_normalize_header(value))
            if field_name and field_name not in columns:
                columns[field_name] = index
        return columns

    def _to_float(self, value):
        if value in (None, ""):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).strip().replace(",", "."))
        except (TypeError, ValueError):
            return None

    def _error_message(self, error):
        message = str(error).strip()
        return message.splitlines()[-1][:500] if message else _("Ошибка импорта.")

    def _create_line(self, vals, status, message):
        self.env["retail.product.import.line"].create(dict(vals, status=status, message=message))


class RetailProductImportLine(models.TransientModel):
    _name = "retail.product.import.line"
    _description = "Строка результата импорта товаров"
    _order = "row_number"

    wizard_id = fields.Many2one(
        "retail.product.import.wizard",
        required=True,
        ondelete="cascade",
        index=True,
    )
    row_number = fields.Integer(string="Строка")
    status = fields.Selection(
        [
            ("imported", "Импортирован"),
            ("skipped", "Пропущен"),
            ("error", "Ошибка"),
        ],
        string="Статус",
        required=True,
    )
    name = fields.Char(string="Название")
    default_code = fields.Char(string="Артикул")
    barcode = fields.Char(string="Штрихкод")
    category_name = fields.Char(string="Категория")
    uom_name = fields.Char(string="Ед. изм.")
    purchase_price = fields.Float(string="Закупочная цена")
    sale_price = fields.Float(string="Розничная цена")
    message = fields.Text(string="Сообщение")
    product_id = fields.Many2one("product.product", string="Товар", readonly=True)
