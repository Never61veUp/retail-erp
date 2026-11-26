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
            "alert_time": 10,
        })
        cls.product = product_template.product_variant_id
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.vendor_location = cls.env.ref("stock.stock_location_suppliers")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.warehouse_user = cls.env["res.users"].with_context(
            no_reset_password=True
        ).create({
            "name": "Пользователь склада для теста",
            "login": "retail-expiry-notification-test",
            "group_ids": [(6, 0, [cls.env.ref("stock.group_stock_user").id])],
            "company_id": cls.env.company.id,
            "company_ids": [(6, 0, [cls.env.company.id])],
        })

    def _create_expiring_lot_with_stock(self, name, expiration_date):
        lot = self.env["stock.lot"].create({
            "name": name,
            "product_id": self.product.id,
            "expiration_date": expiration_date,
        })
        self.env["stock.quant"]._update_available_quantity(
            self.product, self.stock_location, 3, lot_id=lot
        )
        return lot

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

    def test_expiry_alert_notifies_warehouse_user_once_with_lot_details(self):
        expiration_date = fields.Datetime.now() + timedelta(days=5)
        lot = self._create_expiring_lot_with_stock("ПАРТИЯ-УВЕДОМЛЕНИЕ", expiration_date)

        self.env["stock.lot"]._alert_date_exceeded()
        self.env["stock.lot"]._alert_date_exceeded()

        activities = lot.activity_ids.filtered(
            lambda activity: activity.user_id == self.warehouse_user
            and activity.summary == "Приближается срок годности"
        )
        self.assertEqual(len(activities), 1)
        self.assertIn(self.product.display_name, activities.note)
        self.assertIn(lot.name, activities.note)
        self.assertIn("3 %s" % self.product.uom_id.name, activities.note)
        self.assertIn(fields.Datetime.to_string(expiration_date), activities.note)

    def test_expiry_alert_waits_until_configured_alert_date(self):
        expiration_date = fields.Datetime.now() + timedelta(days=20)
        lot = self._create_expiring_lot_with_stock("ПАРТИЯ-БЕЗ-УВЕДОМЛЕНИЯ", expiration_date)

        self.env["stock.lot"]._alert_date_exceeded()

        activities = lot.activity_ids.filtered(
            lambda activity: activity.user_id == self.warehouse_user
            and activity.summary == "Приближается срок годности"
        )
        self.assertFalse(activities)
