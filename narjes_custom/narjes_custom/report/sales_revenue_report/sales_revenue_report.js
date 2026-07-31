// Copyright (c) 2026, Narjes Custom and contributors
// For license information, please see license.txt

frappe.query_reports["Sales Revenue Report"] = {
    filters: [
        {
            fieldname: "customer",
            label: __("Customer"),
            fieldtype: "Link",
            options: "Customer"
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -1)
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today()
        }
    ],

    formatter: function (value, row, column, data, default_formatter) {
        if (column.fieldname === "items_detail" && value) {
            return `<button class="btn btn-xs btn-default items-btn" data-order="${value}">View Items</button>`;
        }

        // Color profit green/red
        if (column.fieldname === "profit") {
            let color = value >= 0 ? "green" : "red";
            return `<span style="color: ${color}; font-weight: bold;">${default_formatter(value, row, column, data)}</span>`;
        }

        if (column.fieldname === "profit_percentage") {
            let color = value >= 0 ? "green" : "red";
            return `<span style="color: ${color};">${default_formatter(value, row, column, data)}</span>`;
        }

        return default_formatter(value, row, column, data);
    },

    onload: function (report) {
        // Attach click handler for "View Items" buttons
        report.$report.on("click", ".items-btn", function () {
            let sales_order = $(this).data("order");
            show_items_dialog(sales_order);
        });
    }
};


function show_items_dialog(sales_order) {
    frappe.call({
        method: "narjes_custom.narjes_custom.report.sales_revenue_report.sales_revenue_report.get_order_items",
        args: { sales_order: sales_order },
        callback: function (r) {
            if (!r.message || r.message.length === 0) {
                frappe.msgprint(__("No items found for this order."));
                return;
            }

            let items = r.message;

            // Build a nice HTML table
            let table_html = `
                <div style="max-height: 400px; overflow-y: auto;">
                <table class="table table-bordered table-striped" style="margin: 0;">
                    <thead style="position: sticky; top: 0; background: var(--bg-color);">
                        <tr>
                            <th>${__("Type")}</th>
                            <th>${__("Item Code")}</th>
                            <th>${__("Item Name")}</th>
                            <th style="text-align: right;">${__("Qty")}</th>
                            <th style="text-align: right;">${__("Selling Rate")}</th>
                            <th style="text-align: right;">${__("Buying Rate")}</th>
                            <th style="text-align: right;">${__("Profit")}</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            let total_selling = 0, total_buying = 0, total_profit = 0;

            items.forEach(function (item) {
                let profit = item.profit || 0;
                let color = profit >= 0 ? "green" : "red";
                total_selling += (item.selling_rate || 0) * (item.qty || 0);
                total_buying += (item.buying_rate || 0) * (item.qty || 0);
                total_profit += profit;

                let is_flower = item.source && item.source !== __("Item");
                table_html += `
                    <tr>
                        <td>${is_flower
                            ? `<span class="indicator-pill green">${frappe.utils.escape_html(item.source)}</span>`
                            : `<span class="text-muted">${frappe.utils.escape_html(item.source || __("Item"))}</span>`}</td>
                        <td>${item.item_code || ""}</td>
                        <td>${item.item_name || ""}</td>
                        <td style="text-align: right;">${item.qty || 0}</td>
                        <td style="text-align: right;">${format_currency(item.selling_rate || 0)}</td>
                        <td style="text-align: right;">${format_currency(item.buying_rate || 0)}</td>
                        <td style="text-align: right; color: ${color}; font-weight: bold;">${format_currency(profit)}</td>
                    </tr>
                `;
            });

            let total_color = total_profit >= 0 ? "green" : "red";
            table_html += `
                    </tbody>
                    <tfoot>
                        <tr style="font-weight: bold; background: var(--bg-color);">
                            <td colspan="4">${__("Total")}</td>
                            <td style="text-align: right;">${format_currency(total_selling)}</td>
                            <td style="text-align: right;">${format_currency(total_buying)}</td>
                            <td style="text-align: right; color: ${total_color};">${format_currency(total_profit)}</td>
                        </tr>
                    </tfoot>
                </table>
                </div>
            `;

            let d = new frappe.ui.Dialog({
                title: __("Items for {0}", [sales_order]),
                size: "large",
                fields: [
                    {
                        fieldtype: "HTML",
                        fieldname: "items_html",
                        options: table_html
                    }
                ]
            });
            d.show();
        }
    });
}
