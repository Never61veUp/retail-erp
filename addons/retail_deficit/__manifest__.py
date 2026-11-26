{
    "name": "Уведомления дефицита",
    "version": "19.0.1.2.0",
    "summary": "Уведомления о низких запасах и заказ поставщику по правилам min/max",
    "author": "",
    "license": "LGPL-3",
    "depends": ["stock", "purchase", "mail", "sale", "point_of_sale"],
    "data": [
        "security/ir.model.access.csv",
        "security/retail_deficit_report_security.xml",
        "data/ir_sequence.xml",
        "data/ir_cron.xml",
        "views/retail_stock_alert_views.xml",
        "views/purchase_discrepancy_views.xml",
        "views/deficit_report_views.xml",
    ],
    "installable": True,
    "application": False,
}
