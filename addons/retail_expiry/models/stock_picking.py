from odoo import _, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _check_retail_expiry_requirements(self):
        now = fields.Datetime.now()
        for picking in self:
            lines = picking.move_line_ids.filtered(
                lambda line: line.product_id.use_expiration_date and line.quantity > 0
            )
            if picking.picking_type_id.code == "incoming":
                errors = []
                for line in lines:
                    if not (line.lot_id or (line.lot_name or "").strip()):
                        errors.append(_("%s: укажите партию.", line.product_id.display_name))
                    if not (line.expiration_date or (line.lot_id and line.lot_id.expiration_date)):
                        errors.append(_("%s: укажите срок годности.", line.product_id.display_name))
                    if not line.location_dest_id or line.location_dest_id.usage != "internal":
                        errors.append(_("%s: укажите складскую локацию.", line.product_id.display_name))
                if errors:
                    raise UserError(
                        _("Невозможно подтвердить приёмку товара со сроком годности:\n%s")
                        % "\n".join(errors)
                    )

            if picking.picking_type_id.code == "outgoing":
                for line in lines:
                    lot = line.lot_id
                    expiration_date = lot.expiration_date if lot else line.expiration_date
                    if not lot or not expiration_date:
                        raise UserError(_(
                            "Нельзя отгрузить товар «%(product)s»: для партии не указан срок годности.",
                            product=line.product_id.display_name,
                        ))
                    if expiration_date <= now:
                        raise UserError(_(
                            "Нельзя отгрузить просроченный товар «%(product)s», партия «%(lot)s».",
                            product=line.product_id.display_name,
                            lot=lot.name,
                        ))

    def _pre_action_done_hook(self):
        self._check_retail_expiry_requirements()
        return super()._pre_action_done_hook()

    def _action_done(self):
        self._check_retail_expiry_requirements()
        return super()._action_done()
