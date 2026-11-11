{
    "name": "Retail Deficit Alerts",
    "version": "19.0.1.0.0",
    "summary": "Low stock alerts and purchase orders from min/max recommendations",
    "author": "",
    "license": "LGPL-3",
    "depends": ["stock", "purchase", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "data/ir_cron.xml",
        "views/retail_stock_alert_views.xml",
    ],
    "installable": True,
    "application": False,
}
