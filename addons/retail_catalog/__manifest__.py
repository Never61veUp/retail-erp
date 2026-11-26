{
    "name": "Retail Catalog",
    "version": "19.0.1.0.0",
    "summary": "Retail product catalog backend",
    "depends": ["product", "uom", "purchase", "stock", "point_of_sale"],
    "data": [
        "views/product_template_views.xml",
        "views/stock_quant_views.xml",
    ],
    "installable": True,
    "application": False,
}
