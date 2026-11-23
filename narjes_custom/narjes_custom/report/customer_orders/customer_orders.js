// Copyright (c) 2026, Narjes Custom and contributors
// For license information, please see license.txt

/* global frappe, __ */

// Select options come from the Sales Order fields themselves, so a governorate
// or order type added later shows up here without touching this file.
function so_options(fieldname) {
	const df = frappe.meta.get_docfield("Sales Order", fieldname);
	return ["", ...((df && df.options) || "").split("\n").filter(Boolean)];
}

frappe.query_reports["Customer Orders"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
			reqd: 1,
		},
		{
			fieldname: "governorate",
			label: __("Governorate"),
			fieldtype: "Select",
			options: so_options("governorate_of_delivery"),
		},
		{
			fieldname: "order_type",
			label: __("Order Type"),
			fieldtype: "Select",
			options: so_options("design_type"),
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
	],

	onload() {
		// The filter options above read Sales Order meta; make sure it is
		// loaded even when this report is the first page opened.
		frappe.model.with_doctype("Sales Order", () => {
			const report = frappe.query_report;
			["governorate", "order_type"].forEach((name) => {
				const field = report.get_filter(name);
				const source = name === "governorate" ? "governorate_of_delivery" : "design_type";
				if (field) {
					field.df.options = so_options(source);
					field.refresh();
				}
			});
		});
	},

	formatter(value, row, column, data, default_formatter) {
		const out = default_formatter(value, row, column, data);
		const name = column.fieldname;
		if (name === "price_with_delivery" || name === "price_without_delivery") {
			const weight = name === "price_without_delivery" ? "font-weight:500;" : "";
			return `<span style="font-variant-numeric:tabular-nums;${weight}">${out}</span>`;
		}
		// Names, addresses and governorates are mostly Arabic: let each cell
		// pick its own direction so the text reads naturally.
		if (["customer_name", "order_type", "governorate", "address"].includes(name) && value) {
			return `<span dir="auto">${out}</span>`;
		}
		if (name === "order_type" && data && !data.order_type && !data.bold) {
			return `<span style="color:var(--text-muted)">—</span>`;
		}
		return out;
	},
};
