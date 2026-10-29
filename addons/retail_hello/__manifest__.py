{
    "name": "Retail Hello",
    "version": "1.0.0",
    "depends": ["base"],
    "data": [
        "views/menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "retail_hello/static/src/js/welcome.js",
            "retail_hello/static/src/xml/welcome.xml",
        ],
    },
    "installable": True,
    "application": True,
}