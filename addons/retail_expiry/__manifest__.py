{
    "name": "Сроки годности и хранение",
    "version": "19.0.1.0.0",
    "summary": "Контроль сроков годности партий и условий хранения товаров",
    "license": "LGPL-3",
    "depends": ["stock", "product_expiry"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_template_views.xml",
        "views/stock_lot_views.xml",
        "wizard/expiry_report_wizard_views.xml",
    ],
    "installable": True,
    "application": True,
}
