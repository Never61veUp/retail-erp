{
    "name": "Retail Catalog",
    "version": "19.0.1.2.0",
    "summary": "Retail product catalog backend",
    "depends": ["product", "uom", "purchase", "stock", "stock_account", "point_of_sale"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_template_views.xml",
        "views/stock_quant_views.xml",
        "views/product_import_views.xml",
    ],
    "installable": True,
    "application": False,
}
