{
    "name": "Уведомления дефицита",
    "version": "19.0.1.0.0",
    "summary": "Уведомления о низких запасах и заказ поставщику по правилам min/max",
    "author": "",
    "license": "LGPL-3",
    "depends": ["stock", "purchase", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "data/ir_cron.xml",
        "views/retail_stock_alert_views.xml",
        "views/purchase_discrepancy_views.xml",
    ],
    "installable": True,
    "application": False,
}
