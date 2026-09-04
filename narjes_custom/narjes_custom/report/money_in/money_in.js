// Copyright (c) 2026, Narjes Custom and contributors
// For license information, please see license.txt

/* global frappe, __ */

frappe.query_reports["Money In"] = {
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
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
	],

	formatter(value, row, column, data, default_formatter) {
		const out = default_formatter(value, row, column, data);
		if (column.fieldname === "amount") {
			return `<span style="font-variant-numeric:tabular-nums;color:var(--green-600);font-weight:500">${out}</span>`;
		}
		return out;
	},
};
