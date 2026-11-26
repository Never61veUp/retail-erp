from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRetailExpiry(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.env.company.id)], limit=1
        )
        product_template = cls.env["product.template"].create({
            "name": "Тестовый скоропортящийся товар",
            "is_storable": True,
            "tracking": "lot",
            "use_expiration_date": True,
            "expiration_time": 30,
        })
        cls.product = product_template.product_variant_id
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.vendor_location = cls.env.ref("stock.stock_location_suppliers")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")

    def _create_picking_with_line(self, code, location, destination, lot_name=False, expiry=False):
        picking_type = (
            self.warehouse.in_type_id if code == "incoming" else self.warehouse.out_type_id
        )
        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "location_id": location.id,
            "location_dest_id": destination.id,
        })
        move = self.env["stock.move"].create({
            "name": self.product.display_name,
            "product_id": self.product.id,
            "product_uom": self.product.uom_id.id,
            "product_uom_qty": 1,
            "location_id": location.id,
            "location_dest_id": destination.id,
            "picking_id": picking.id,
        })
        line = self.env["stock.move.line"].create({
            "move_id": move.id,
            "product_id": self.product.id,
            "product_uom_id": self.product.uom_id.id,
            "quantity": 1,
            "location_id": location.id,
            "location_dest_id": destination.id,
            "lot_name": lot_name or False,
            "expiration_date": expiry or False,
        })
        return picking, line

    def test_receipt_requires_lot_number(self):
        picking, line = self._create_picking_with_line(
            "incoming", self.vendor_location, self.stock_location
        )
        line.write({"expiration_date": False})

        with self.assertRaisesRegex(UserError, "укажите партию"):
            picking._check_retail_expiry_requirements()

    def test_receipt_requires_expiration_date(self):
        picking, line = self._create_picking_with_line(
            "incoming",
            self.vendor_location,
            self.stock_location,
            lot_name="ПАРТИЯ-БЕЗ-СРОКА",
        )
        line.write({"expiration_date": False})

        with self.assertRaisesRegex(UserError, "укажите срок годности"):
            picking._check_retail_expiry_requirements()

    def test_receipt_requires_internal_warehouse_location(self):
        picking, _line = self._create_picking_with_line(
            "incoming",
            self.vendor_location,
            self.customer_location,
            lot_name="ПАРТИЯ-БЕЗ-СКЛАДА",
            expiry=fields.Datetime.now() + timedelta(days=10),
        )

        with self.assertRaisesRegex(UserError, "укажите складскую локацию"):
            picking._check_retail_expiry_requirements()

    def test_receipt_accepts_complete_lot_information(self):
        picking, _line = self._create_picking_with_line(
            "incoming",
            self.vendor_location,
            self.stock_location,
            lot_name="ПАРТИЯ-001",
            expiry=fields.Datetime.now() + timedelta(days=10),
        )

        picking._check_retail_expiry_requirements()

    def test_expired_lot_cannot_be_shipped(self):
        lot = self.env["stock.lot"].create({
            "name": "ПАРТИЯ-ПРОСРОЧЕНА",
            "product_id": self.product.id,
            "expiration_date": fields.Datetime.now() - timedelta(days=1),
        })
        picking, line = self._create_picking_with_line(
            "outgoing", self.stock_location, self.customer_location
        )
        line.write({"lot_id": lot.id, "lot_name": False})

        with self.assertRaisesRegex(UserError, "Нельзя отгрузить просроченный товар"):
            picking._check_retail_expiry_requirements()
