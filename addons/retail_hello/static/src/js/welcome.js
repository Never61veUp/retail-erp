import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class RetailHello extends Component {
    static template = "retail_hello.Welcome";
}

registry.category("actions").add(
    "retail_hello.welcome",
    RetailHello
);
