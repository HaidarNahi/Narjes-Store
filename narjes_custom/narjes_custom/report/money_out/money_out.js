// Copyright (c) 2026, Narjes Custom and contributors
// For license information, please see license.txt

/* global frappe, __ */

frappe.query_reports["Money Out"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			// The calendar month the shop is living in, which is how they
			// read every other number in this system.
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
			fieldname: "bucket",
			label: __("Kind"),
			fieldtype: "Select",
			options: [
				{ value: "", label: __("Everything") },
				{ value: "Direct", label: __("Cost of goods") },
				{ value: "Operating", label: __("Running the shop") },
				{ value: "Correction", label: __("Stock corrections") },
			],
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
			// A stock correction is not money the shop spent, so it must not
			// read like the rows above and below it that are.
			const muted = data && data.bucket === "Correction";
			return `<span style="font-variant-numeric:tabular-nums;${
				muted ? "color:var(--text-muted)" : "color:var(--red-600);font-weight:500"
			}">${out}</span>`;
		}

		if (column.fieldname === "bucket" && value) {
			const tone = {
				Direct: "orange",
				Operating: "blue",
				Correction: "gray",
			}[value] || "gray";
			const label = {
				Direct: __("Cost of goods"),
				Operating: __("Running the shop"),
				Correction: __("Correction"),
			}[value] || value;
			return `<span class="indicator-pill ${tone}">${label}</span>`;
		}

		return out;
	},
};
